import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os

# --- Configuration (Pre-set from your feedback.db) ---
DB_NAME = "feedback.db"
TABLE_NAME = "reviews" # 
QUERY = "SELECT id, review_text FROM reviews" # 

# Define the columns for the display table
# ('internal_name', 'Display Name', width_in_pixels)
COLUMN_CONFIG = [
    ('id', 'ID', 50),
    ('review', 'Review Text', 700) # 
]
# --- End of Configuration ---


def load_feedback():
    """
    Connects to the database, fetches the data, and populates the treeview.
    """
    # Clear any existing data from the tree first
    for row in tree.get_children():
        tree.delete(row)

    # Check if the database file exists
    if not os.path.exists(DB_NAME):
        messagebox.showerror("Error", f"Database file not found: {DB_NAME}\n"
                                     "Please place it in the same folder as the script.")
        return

    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Execute the query
        cursor.execute(QUERY)
        rows = cursor.fetchall()

        # Check if any data was returned
        if not rows:
            messagebox.showinfo("Info", "No data found in the table.")
        else:
            # Insert data into the treeview
            for row in rows:
                tree.insert('', tk.END, values=row)

    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"An error occurred: {e}\n\n"
                                               f"Could not read table '{TABLE_NAME}'.")
    finally:
        # Always close the connection
        if 'conn' in locals():
            conn.close()

# --- Set up the main application window ---
root = tk.Tk()
root.title("Feedback Database Viewer")
root.geometry("850x500")

# --- Create the Frame for the Treeview and Scrollbars ---
frame = ttk.Frame(root, padding="10")
frame.pack(fill="both", expand=True)

# --- Create Scrollbars ---
# Vertical Scrollbar
yscrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL)

# Horizontal Scrollbar (for the long review text)
xscrollbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)

# --- Create the Treeview (table display) ---
column_ids = [c[0] for c in COLUMN_CONFIG] 
tree = ttk.Treeview(frame, 
                    columns=column_ids, 
                    show='headings', 
                    yscrollcommand=yscrollbar.set, 
                    xscrollcommand=xscrollbar.set)

# Link scrollbars to the treeview
yscrollbar.config(command=tree.yview)
xscrollbar.config(command=tree.xview)

# Configure the headings and column widths
for col_id, display_name, width in COLUMN_CONFIG:
    tree.heading(col_id, text=display_name)
    tree.column(col_id, width=width, minwidth=50)

# --- Lay out the widgets using pack ---
# Pack scrollbars first
yscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
xscrollbar.pack(side=tk.BOTTOM, fill=tk.X)

# Pack the tree to fill the remaining space
tree.pack(side=tk.LEFT, fill="both", expand=True)

# --- Create the "Load" Button ---
load_button = ttk.Button(root, text="Load Feedback", command=load_feedback)
load_button.pack(pady=10)

# --- Start the GUI event loop ---
root.mainloop()