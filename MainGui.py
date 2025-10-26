import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sqlite3
import threading
import json
from openai import OpenAI
from collections import Counter

# --- Plotting & Visualization Imports ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from wordcloud import WordCloud

# --- Import API Key ---
try:
    import TommysAPIKey
    apikey = TommysAPIKey.OPEN_AI_KEY
except ImportError:
    # This will show a popup error if the key file is missing
    messagebox.showerror("Error", "Could not find APIKey.py or OPEN_AI_KEY variable.\nPlease make sure the file exists in the same directory.")
    exit()

# --- Main Application Class ---

class ReviewAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Apple Vision Pro - Review Analyzer")
        self.root.geometry("800x600")

        # --- Main Layout ---
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 1. Top Frame: Button
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        self.analyze_button = tk.Button(top_frame, text="Analyze All Customer Reviews", 
                                        font=("Arial", 12, "bold"), command=self.start_analysis_thread)
        self.analyze_button.pack(fill=tk.X)

        # 2. Middle Frame: Tabbed Interface for Results
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tab 1: Summary & Recommendations
        self.tab_summary = scrolledtext.ScrolledText(self.notebook, wrap=tk.WORD, font=("Arial", 11))
        self.tab_summary.insert(tk.END, "Click the 'Analyze' button to load and process reviews.\n\nResults will appear here.")
        self.notebook.add(self.tab_summary, text="Summary & Recommendations")

        # Tab 2: Sentiment Distribution
        self.tab_sentiment = tk.Frame(self.notebook)
        self.notebook.add(self.tab_sentiment, text="Sentiment")

        # Tab 3: Positive Aspects (Word Cloud)
        self.tab_pos_aspects = tk.Frame(self.notebook)
        self.notebook.add(self.tab_pos_aspects, text="Positive Aspects")
        
        # Tab 4: Negative Aspects (Word Cloud)
        self.tab_neg_aspects = tk.Frame(self.notebook)
        self.notebook.add(self.tab_neg_aspects, text="Negative Aspects")

        # Tab 5: All Reviews (Raw Data)
        self.tab_all_reviews = scrolledtext.ScrolledText(self.notebook, wrap=tk.WORD, font=("Arial", 10))
        self.notebook.add(self.tab_all_reviews, text="All Reviews")

        # 3. Bottom Frame: Status Bar
        self.status_label = tk.Label(main_frame, text="Ready. (Make sure feedback.db is in the same folder)", 
                                     bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Initialize OpenAI Client ---
        self.client = OpenAI(
            api_key = apikey
        )

    def update_status(self, message):
        """Safely update the status bar from any thread."""
        self.root.after(0, lambda: self.status_label.config(text=message))

    def start_analysis_thread(self):
        """
        This function is called by the button.
        It starts the long-running analysis in a new thread
        to keep the GUI responsive.
        """
        self.analyze_button.config(state="disabled", text="Analyzing... Please Wait...")
        self.clear_previous_results()
        
        # Start the background thread
        thread = threading.Thread(target=self.run_analysis)
        thread.start()

    def clear_previous_results(self):
        """Clears all text and charts from the tabs."""
        self_tabs = [self.tab_summary, self.tab_all_reviews]
        for tab in self_tabs:
            tab.delete("1.0", tk.END)

        chart_tabs = [self.tab_sentiment, self.tab_pos_aspects, self.tab_neg_aspects]
        for tab in chart_tabs:
            for widget in tab.winfo_children():
                widget.destroy()

    def run_analysis(self):
        """
        This is the main background function.
        It loads, loops, analyzes, and then updates the GUI.
        """
        try:
            # --- 1. Load Data from Database ---
            self.update_status("Connecting to database 'feedback.db'...")
            # CRITICAL: This assumes your table is 'reviews' and column is 'review_text'
            conn = sqlite3.connect('feedback.db')
            cursor = conn.cursor()
            cursor.execute("SELECT review_text FROM reviews")
            all_reviews_text = cursor.fetchall() # List of tuples, e.g., [('review 1',), ('review 2',)]
            conn.close()

            if not all_reviews_text:
                self.update_status("Error: No reviews found in 'feedback.db'.")
                self.root.after(0, lambda: self.analyze_button.config(state="normal", text="Analyze All Customer Reviews"))
                return

            self.update_status(f"Loaded {len(all_reviews_text)} reviews.")

            # --- 2. Analyze Each Review (Sentiment + Aspects) ---
            all_results = []
            all_sentiments = []
            all_aspects = []
            
            for i, (review_text,) in enumerate(all_reviews_text):
                self.update_status(f"Analyzing review {i+1} of {len(all_reviews_text)}...")
                
                # This function calls the OpenAI API
                analysis = self.analyze_single_review(review_text)
                
                if analysis:
                    all_results.append((review_text, analysis))
                    all_sentiments.append(analysis.get('sentiment', 'neutral'))
                    all_aspects.extend(analysis.get('aspects', []))

            self.update_status("All reviews analyzed. Processing results...")

            # --- 3. Process Data for Visualization ---
            sentiment_counts = Counter(all_sentiments)
            
            # Separate aspects by sentiment
            pos_aspect_words = [a['feature'] for a in all_aspects if a['sentiment'] == 'positive']
            neg_aspect_words = [a['feature'] for a in all_aspects if a['sentiment'] == 'negative']

            # --- 4. Generate Final Summary & Recommendations (Another AI Call) ---
            self.update_status("Generating final summary and recommendations...")
            summary_prompt = self.create_summary_prompt(sentiment_counts, pos_aspect_words, neg_aspect_words)
            final_summary = self.get_final_summary(summary_prompt)

            # --- 5. Update GUI with all results ---
            # We must schedule GUI updates on the main thread using root.after
            self.root.after(0, self.populate_gui, final_summary, sentiment_counts, 
                            pos_aspect_words, neg_aspect_words, all_results)

            self.update_status(f"Analysis complete! Processed {len(all_reviews_text)} reviews.")

        except sqlite3.OperationalError as e:
            self.update_status(f"Database Error: {e}. Check 'feedback.db', table 'reviews', or column 'review_text'.")
        except Exception as e:
            self.update_status(f"An unexpected error occurred: {e}")
        finally:
            # Re-enable the button
            self.root.after(0, lambda: self.analyze_button.config(state="normal", text="Analyze All Customer Reviews"))

    def analyze_single_review(self, review_text):
        """
        Calls OpenAI API using JSON mode to get structured data
        for a single review.
        """
        system_prompt = """
        You are an expert review analyst. Analyze the following customer review 
        for the Apple Vision Pro.
        
        You MUST return a JSON object with the following schema:
        {
          "sentiment": "positive | negative | neutral",
          "aspects": [
            {
              "feature": "the specific product feature mentioned (e.g., 'display', 'price', 'battery life', 'comfort')",
              "sentiment": "positive | negative | neutral",
              "quote": "a brief quote from the review supporting this"
            }
          ]
        }
        
        If no specific aspects are mentioned, return an empty "aspects" list.
        """
        
        try:
            # This is the modern, correct API call
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"}, # Use JSON mode
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": review_text}
                ]
            )
            # Parse the JSON string from the response
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"Error analyzing review: {e}") # Log to console
            return None # Skip this review on error

    def create_summary_prompt(self, sentiment_counts, pos_aspects, neg_aspects):
        """Creates the prompt for the final high-level summary."""
        prompt = f"""
        Analyze the following aggregated review data for the Apple Vision Pro.

        Overall Sentiment Distribution:
        {dict(sentiment_counts)}

        Frequently Mentioned Positive Aspects/Features:
        {Counter(pos_aspects).most_common(10)}

        Frequently Mentioned Negative Aspects/Features:
        {Counter(neg_aspects).most_common(10)}

        Based on this data, please provide a high-level summary.
        Your response MUST be formatted as follows:

        **Executive Summary:**
        [A one-paragraph summary of the overall customer sentiment.]

        **Key Strengths (What Customers Love):**
        [A bulleted list of the top 3-5 positive aspects and why.]

        **Key Weaknesses (What Customers Dislike):**
        [A bulleted list of the top 3-5 negative aspects and why.]

        **Actionable Recommendations:**
        [A bulleted list of specific, actionable recommendations for product improvement based *only* on the data provided.]
        """
        return prompt

    def get_final_summary(self, prompt):
        """Calls the AI one last time to get the final summary."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior product analyst."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating final summary: {e}"

    def populate_gui(self, summary, sentiment_counts, pos_words, neg_words, all_results):
        """
        This function is called on the main thread to safely
        update all the GUI tabs with the final data.
        """
        # 1. Populate Summary Tab
        self.tab_summary.delete("1.0", tk.END)
        self.tab_summary.insert(tk.END, summary)

        # 2. Populate Sentiment Tab (Bar Chart)
        self.draw_sentiment_chart(sentiment_counts)
        
        # 3. Populate Word Clouds
        self.draw_word_cloud(self.tab_pos_aspects, pos_words, 'Positive Aspects')
        self.draw_word_cloud(self.tab_neg_aspects, neg_words, 'Negative Aspects')

        # 4. Populate All Reviews Tab
        self.tab_all_reviews.delete("1.0", tk.END)
        for i, (review, analysis) in enumerate(all_results):
            self.tab_all_reviews.insert(tk.END, f"--- REVIEW {i+1} ---\n", ("h1",))
            self.tab_all_reviews.insert(tk.END, f"{review}\n\n")
            self.tab_all_reviews.insert(tk.END, f"Sentiment: {analysis.get('sentiment', 'N/A')}\n", ("bold",))
            self.tab_all_reviews.insert(tk.END, "Aspects:\n")
            for aspect in analysis.get('aspects', []):
                self.tab_all_reviews.insert(tk.END, f"  - {aspect.get('feature')}: {aspect.get('sentiment')}\n")
            self.tab_all_reviews.insert(tk.END, "\n\n")
        
        self.tab_all_reviews.tag_config("h1", font=("Arial", 12, "bold"))
        self.tab_all_reviews.tag_config("bold", font=("Arial", 10, "bold"))

    def draw_sentiment_chart(self, counts):
        """Draws the matplotlib bar chart in the Sentiment tab."""
        # Clear previous chart
        for widget in self.tab_sentiment.winfo_children():
            widget.destroy()

        labels = list(counts.keys())
        values = list(counts.values())
        colors = ['#4CAF50' if l == 'positive' else '#F44336' if l == 'negative' else '#FFC107' for l in labels]
        
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.bar(labels, values, color=colors)
        ax.set_title('Sentiment Distribution')
        ax.set_ylabel('Number of Reviews')
        
        # Embed the chart in tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.tab_sentiment)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def draw_word_cloud(self, tab, words_list, title):
        """Draws the matplotlib word cloud in the specified tab."""
        # Clear previous chart
        for widget in tab.winfo_children():
            widget.destroy()

        if not words_list:
            tk.Label(tab, text=f"No {title.lower()} found.").pack(pady=20)
            return

        text = " ".join(words_list)
        wordcloud = WordCloud(width=400, height=300, background_color='white').generate(text)
        
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.set_title(title)
        ax.axis('off')
        
        # Embed the chart in tkinter
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# --- Run the Application ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ReviewAnalyzerApp(root)
    root.mainloop()