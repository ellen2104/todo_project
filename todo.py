import os
import mysql.connector as conn
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv

# Load database configuration from .env file
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "todo_db")


########################################
# DATABASE CONNECTION
########################################

def get_con():
    """Establish and return a connection to MySQL database."""
    try:
        return conn.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except Error as e:
        # Avoid leaking sensitive credentials in error message
        print(f"\n[Database Error] Could not connect to MySQL server: {e.msg}")
        return None


########################################
# CREATE TABLE / VERIFY SCHEMA
########################################

def create_table():
    """Create the Tasks table if it does not already exist."""
    db = get_con()
    if not db:
        print("Skipping table creation due to connection failure.")
        return

    cursor = db.cursor()
    try:
        q = """
        CREATE TABLE IF NOT EXISTS Tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            Title VARCHAR(255) NOT NULL,
            Description TEXT,
            Completed BOOLEAN DEFAULT 0,
            CreatedDT DATETIME,
            DueDT DATETIME,
            CompletedDT DATETIME
        )
        """
        cursor.execute(q)
        db.commit()
    except Error as e:
        print(f"[Database Error] Error initializing table: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# STATUS HELPER
########################################

def print_status(cursor):
    """Print operation status based on affected rows."""
    if cursor.rowcount == 0:
        print("No task was updated or task not found.")
    else:
        print("Operation completed successfully.")


########################################
# DISPLAY TASK HELPER
########################################

def display_tasks(records):
    """Format and print task records consistently across view and search."""
    if not records:
        print("\nNo tasks found.\n")
        return

    for task in records:
        task_id = task[0]
        title = task[1]
        description = task[2]
        completed = task[3]
        created_dt = task[4]
        due_dt = task[5]
        completed_dt = task[6]

        print(f"ID          : {task_id}")
        print(f"Title       : {title}")
        print("Description :")

        if description is None or description.strip() == "":
            print("    (No description)")
        else:
            lines = description.split("\n")
            for line in lines:
                print(f"    {line}")

        status_str = "Completed" if completed else "Pending"
        print(f"Status      : {status_str}")

        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S") if created_dt else "N/A"
        due_str = due_dt.strftime("%Y-%m-%d %H:%M") if due_dt else "N/A"
        completed_str = completed_dt.strftime("%Y-%m-%d %H:%M:%S") if completed_dt else "N/A"

        print(f"Created At  : {created_str}")
        print(f"Due Date    : {due_str}")
        if completed:
            print(f"Completed At: {completed_str}")

        print("-" * 40)


########################################
# VIEW TASKS
########################################

def view_tasks():
    """Retrieve and display all tasks."""
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, Title, Description, Completed, CreatedDT, DueDT, CompletedDT FROM Tasks")
        records = cursor.fetchall()

        if not records:
            print("\nNo tasks found.\n")
            return

        print("\n========== TO DO LIST ==========\n")
        display_tasks(records)
    except Error as e:
        print(f"[Database Error] Could not retrieve tasks: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# ADD TASK
########################################

def add_tasks():
    """Add a new task with title, due date, multi-line description, and creation timestamp."""
    # 1. Validate Title
    while True:
        t = input("Enter the title (or 'cancel' to abort): ").strip()
        if t.lower() == "cancel":
            print("Task creation cancelled.")
            return
        if not t:
            print("Title cannot be empty. Please enter a valid title.")
            continue
        break

    # 2. Validate Due Date
    due_dt_value = None
    while True:
        p = input("Enter Due Date (YYYY-MM-DD HH:MM) [Press Enter to skip]: ").strip()
        if not p:
            break
        try:
            parsed_due = datetime.strptime(p, "%Y-%m-%d %H:%M")
            due_dt_value = parsed_due.strftime("%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            print("Invalid date format. Please use 'YYYY-MM-DD HH:MM' or leave blank.")

    # 3. Enter Description
    print("\nEnter the description (press Enter then type END on a new line when finished).")
    print("If you want an empty description, type END immediately.\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    description = "\n".join(lines) if lines else None
    created_dt_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 4. Insert into database once
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        q = """
        INSERT INTO Tasks (Title, Description, Completed, CreatedDT, DueDT)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(q, (t, description, 0, created_dt_value, due_dt_value))
        db.commit()
        print(f"\nTask '{t}' added successfully with ID: {cursor.lastrowid}")
    except Error as e:
        print(f"[Database Error] Failed to add task: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# MARK COMPLETED / CHANGE STATUS
########################################

def mark_change():
    """Mark a task as completed or pending, updating the completion timestamp."""
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        while True:
            task_id = input("\nEnter Task ID to update status (or 'cancel' to exit): ").strip()
            if task_id.lower() == "cancel":
                break
            if not task_id.isdigit():
                print("Invalid ID. Please enter a numeric Task ID.")
                continue

            cursor.execute("SELECT id, Title, Completed FROM Tasks WHERE id = %s", (int(task_id),))
            task = cursor.fetchone()
            if not task:
                print(f"Task ID {task_id} not found.")
                continue

            current_status = "Completed" if task[2] else "Pending"
            print(f"Task [{task[0]}] '{task[1]}' is currently {current_status}.")
            print("1. Mark as Completed")
            print("2. Mark as Pending")
            print("3. Cancel")
            sub_ch = input("Enter choice (1-3): ").strip()

            if sub_ch == "1":
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                q = "UPDATE Tasks SET Completed = 1, CompletedDT = %s WHERE id = %s"
                cursor.execute(q, (now_str, int(task_id)))
                db.commit()
                print(f"Task {task_id} marked as Completed at {now_str}.")
            elif sub_ch == "2":
                q = "UPDATE Tasks SET Completed = 0, CompletedDT = NULL WHERE id = %s"
                cursor.execute(q, (int(task_id),))
                db.commit()
                print(f"Task {task_id} marked as Pending.")
            elif sub_ch == "3":
                pass
            else:
                print("Invalid choice.")

            ch = input("\nUpdate another task status? (y/n): ").strip()
            if ch.lower() != "y":
                break
    except Error as e:
        print(f"[Database Error] Error updating task status: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# DELETE TASK
########################################

def del_task():
    """Delete a task by ID."""
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        while True:
            task_id = input("\nEnter Task ID to delete (or 'cancel' to exit): ").strip()
            if task_id.lower() == "cancel":
                break
            if not task_id.isdigit():
                print("Invalid ID. Please enter a numeric Task ID.")
                continue

            # Check if task exists first
            cursor.execute("SELECT Title FROM Tasks WHERE id = %s", (int(task_id),))
            row = cursor.fetchone()
            if not row:
                print("Task not found.")
                continue

            confirm = input(f"Are you sure you want to delete task '{row[0]}'? (y/n): ").strip()
            if confirm.lower() != "y":
                print("Deletion cancelled.")
                continue

            q = "DELETE FROM Tasks WHERE id = %s"
            cursor.execute(q, (int(task_id),))
            db.commit()
            print_status(cursor)

            ch = input("\nDelete another task? (y/n): ").strip()
            if ch.lower() != "y":
                break
    except Error as e:
        print(f"[Database Error] Failed to delete task: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# UPDATE DESCRIPTION IN DATABASE
########################################

def save_description(db, cursor, task_id, lines):
    """Save the joined description lines to MySQL for the given task ID."""
    description = "\n".join(lines) if lines else None
    q = """
    UPDATE Tasks
    SET Description = %s
    WHERE id = %s
    """
    cursor.execute(q, (description, task_id))
    db.commit()
    print_status(cursor)


########################################
# EDIT TITLE
########################################

def edit_title(db, cursor, task_id):
    """Edit the title of the selected task."""
    ch = input("Do you want to edit the title? (y/n): ").strip()
    if ch.lower() != "y":
        return

    while True:
        title = input("Enter new title: ").strip()
        if not title:
            print("Title cannot be empty.")
            continue
        break

    q = """
    UPDATE Tasks
    SET Title = %s
    WHERE id = %s
    """
    cursor.execute(q, (title, task_id))
    db.commit()
    print_status(cursor)


########################################
# REWRITE ENTIRE DESCRIPTION
########################################

def new_description(db, cursor, task_id):
    """Prompt user to rewrite the entire description and update MySQL."""
    print("\nEnter the new description.")
    print("Type END on a new line when you are finished.\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    save_description(db, cursor, task_id, lines)
    return lines


########################################
# DELETE A LINE
########################################

def del_line(db, cursor, task_id, lines, line_no):
    """Delete line at line_no (1-indexed) and save."""
    del lines[line_no - 1]
    save_description(db, cursor, task_id, lines)


########################################
# REWRITE A LINE
########################################

def new_line(db, cursor, task_id, lines, line_no):
    """Rewrite line at line_no (1-indexed) and save."""
    new_text = input("Enter new line: ")
    lines[line_no - 1] = new_text
    save_description(db, cursor, task_id, lines)


########################################
# REPLACE A WORD
########################################

def rewrite_word(db, cursor, task_id, lines):
    """Replace a specific word in a given line of the description."""
    if not lines:
        print("Description is empty. No lines to edit.")
        return

    print("\nCurrent lines:")
    for i, line in enumerate(lines, start=1):
        print(f"  {i}: {line}")

    line_input = input("\nEnter line number to edit: ").strip()
    if not line_input.isdigit():
        print("Invalid line number. Must be numeric.")
        return

    line_no = int(line_input)
    if not (1 <= line_no <= len(lines)):
        print(f"Invalid line number. Please choose between 1 and {len(lines)}.")
        return

    old_word = input("Old word to replace: ")
    if old_word not in lines[line_no - 1]:
        print(f"Word '{old_word}' not found in line {line_no}.")
        return

    new_word = input("New word: ")

    print("\nBefore:")
    print(lines[line_no - 1])

    lines[line_no - 1] = lines[line_no - 1].replace(old_word, new_word)

    print("\nAfter:")
    print(lines[line_no - 1])

    save_description(db, cursor, task_id, lines)


########################################
# ADD NEW LINE
########################################

def add_line(db, cursor, task_id, lines):
    """Insert a new line at a specified position in description."""
    if not lines:
        print("Description is currently empty. The new line will be the first line.")
        insert_idx = 0
    else:
        print("\nCurrent lines:")
        for i, line in enumerate(lines, start=1):
            print(f"  {i}: {line}")

        pos_input = input(f"After which line do you want to insert? (0 for top, 1-{len(lines)}): ").strip()
        if not pos_input.isdigit():
            print("Invalid input. Must be a number.")
            return

        after_line = int(pos_input)
        if not (0 <= after_line <= len(lines)):
            print(f"Invalid position. Must be between 0 and {len(lines)}.")
            return
        insert_idx = after_line

    new_content = input("Enter new line: ")
    lines.insert(insert_idx, new_content)

    save_description(db, cursor, task_id, lines)


########################################
# EDIT A LINE MENU
########################################

def edit_line(db, cursor, task_id, lines):
    """Menu to delete or rewrite a specific line in the description."""
    if not lines:
        print("Description is empty. No lines to edit.")
        return

    print("\nCurrent lines:")
    for i, line in enumerate(lines, start=1):
        print(f"  {i}: {line}")

    line_input = input("\nEnter line number: ").strip()
    if not line_input.isdigit():
        print("Invalid line number. Must be numeric.")
        return

    line_no = int(line_input)
    if not (1 <= line_no <= len(lines)):
        print(f"Invalid line number. Must be between 1 and {len(lines)}.")
        return

    print("\n1. Delete Line")
    print("2. Rewrite Line")
    print("3. Cancel")

    ch = input("Enter choice (1-3): ").strip()
    if ch == "1":
        del_line(db, cursor, task_id, lines, line_no)
    elif ch == "2":
        new_line(db, cursor, task_id, lines, line_no)
    elif ch == "3":
        return
    else:
        print("Invalid choice.")


########################################
# EDIT DESCRIPTION MENU
########################################

def edit_description(db, cursor, task_id):
    """Submenu for editing various aspects of the task description."""
    q = "SELECT Description FROM Tasks WHERE id = %s"
    cursor.execute(q, (task_id,))
    record = cursor.fetchone()

    if record is None:
        print("Task not found.")
        return

    description = record[0]
    if description is None:
        lines = []
    else:
        lines = description.split("\n")

    while True:
        print("\n========= EDIT DESCRIPTION =========")
        print("1. Rewrite Entire Description")
        print("2. Edit a Line (Delete / Rewrite)")
        print("3. Replace a Word")
        print("4. Add New Line")
        print("5. Back to Edit Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == "1":
            lines = new_description(db, cursor, task_id)
        elif choice == "2":
            edit_line(db, cursor, task_id, lines)
        elif choice == "3":
            rewrite_word(db, cursor, task_id, lines)
        elif choice == "4":
            add_line(db, cursor, task_id, lines)
        elif choice == "5":
            return
        else:
            print("Invalid choice.")


########################################
# EDIT TASK
########################################

def edit_task():
    """Main edit workflow allowing title and description modifications."""
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        while True:
            task_id = input("\nEnter Task ID to edit (or 'cancel' to exit): ").strip()
            if task_id.lower() == "cancel":
                break
            if not task_id.isdigit():
                print("Invalid Task ID. Please enter a valid number.")
                continue

            cursor.execute(
                "SELECT id, Title, Description FROM Tasks WHERE id = %s",
                (int(task_id),)
            )
            task = cursor.fetchone()

            if task is None:
                print(f"Task with ID {task_id} not found.")
                continue

            print(f"\nEditing Task ID {task[0]}: '{task[1]}'")
            print("\n========== EDIT MENU ==========")
            print("1. Edit Title")
            print("2. Edit Description")
            print("3. Edit Both")
            print("4. Exit")

            choice = input("Enter your choice (1-4): ").strip()

            if choice == "1":
                edit_title(db, cursor, int(task_id))
            elif choice == "2":
                edit_description(db, cursor, int(task_id))
            elif choice == "3":
                edit_title(db, cursor, int(task_id))
                edit_description(db, cursor, int(task_id))
            elif choice == "4":
                return
            else:
                print("Invalid Choice.")

            more = input("\nDo you want to edit another task? (y/n): ").strip()
            if more.lower() != "y":
                return
    except Error as e:
        print(f"[Database Error] Error during edit: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# SEARCH TITLE
########################################

def search_title():
    """Search tasks by title keyword."""
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        t = input("Enter keyword or title to search: ").strip()
        if not t:
            print("Search keyword cannot be empty.")
            return

        cursor.execute(
            "SELECT id, Title, Description, Completed, CreatedDT, DueDT, CompletedDT FROM Tasks WHERE Title LIKE %s",
            (f"%{t}%",)
        )
        records = cursor.fetchall()

        print("\n========== SEARCH RESULTS (TITLE) ==========\n")
        display_tasks(records)
    except Error as e:
        print(f"[Database Error] Search failed: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# SEARCH STATUS
########################################

def search_status():
    """Search tasks by completion status (0 = Pending, 1 = Completed)."""
    db = get_con()
    if not db:
        return

    cursor = db.cursor()
    try:
        print("\n0. List Pending tasks")
        print("1. List Completed tasks")
        ch = input("Enter your choice (0 or 1): ").strip()

        if ch not in ("0", "1"):
            print("Invalid choice. Please enter 0 or 1.")
            return

        status_val = int(ch)
        cursor.execute(
            "SELECT id, Title, Description, Completed, CreatedDT, DueDT, CompletedDT FROM Tasks WHERE Completed = %s",
            (status_val,)
        )
        records = cursor.fetchall()

        label = "COMPLETED" if status_val == 1 else "PENDING"
        print(f"\n========== SEARCH RESULTS ({label} TASKS) ==========\n")
        display_tasks(records)
    except Error as e:
        print(f"[Database Error] Search failed: {e.msg}")
    finally:
        cursor.close()
        db.close()


########################################
# SEARCH TASKS MENU
########################################

def search_tasks():
    """Submenu for search options."""
    while True:
        print("\n========== SEARCH MENU ==========")
        print("1. Search by Title")
        print("2. Search by Completion Status")
        print("3. Exit to Main Menu")

        choice = input("Enter choice (1-3): ").strip()

        if choice == "1":
            search_title()
        elif choice == "2":
            search_status()
        elif choice == "3":
            break
        else:
            print("Invalid choice. Please select 1, 2, or 3.")


########################################
# MAIN MENU
########################################

def main_menu():
    """Main menu loop for the application."""
    create_table()

    while True:
        print("\n" + "=" * 45)
        print("        TO DO LIST MANAGEMENT")
        print("=" * 45)

        print("1. Add Task")
        print("2. View Tasks")
        print("3. Edit Task")
        print("4. Delete Task")
        print("5. Mark Task as Completed / Change Status")
        print("6. Search Tasks")
        print("7. Exit")

        choice = input("\nEnter your choice (1-7): ").strip()

        if choice == "1":
            add_tasks()
        elif choice == "2":
            view_tasks()
        elif choice == "3":
            edit_task()
        elif choice == "4":
            del_task()
        elif choice == "5":
            mark_change()
        elif choice == "6":
            search_tasks()
        elif choice == "7":
            print("\nThank you for using To-Do List.\n")
            break
        else:
            print("\nInvalid choice. Please enter a number between 1 and 7.\n")


if __name__ == "__main__":
    main_menu()
