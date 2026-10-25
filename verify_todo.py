import io
import sys
import unittest
from unittest.mock import patch
from datetime import datetime
import mysql.connector

# Import modules from todo.py
import todo

class TestTodoList(unittest.TestCase):

    def setUp(self):
        # Ensure table exists
        todo.create_table()
        self.created_test_ids = []

    def tearDown(self):
        # Clean up ONLY the test tasks created during testing
        if self.created_test_ids:
            db = todo.get_con()
            if db:
                cursor = db.cursor()
                format_strings = ','.join(['%s'] * len(self.created_test_ids))
                cursor.execute(f"DELETE FROM Tasks WHERE id IN ({format_strings})", tuple(self.created_test_ids))
                db.commit()
                cursor.close()
                db.close()

    def test_01_add_task_multiline(self):
        """1. Adding a task with a multi-line description."""
        title = "[TEST] Multi-line Task"
        inputs = [
            title,
            "2026-12-31 23:59",  # Due date
            "First line of description",
            "Second line of description",
            "Third line of description",
            "END"
        ]
        with patch('builtins.input', side_effect=inputs):
            todo.add_tasks()

        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("SELECT id, Title, Description, CreatedDT, DueDT FROM Tasks WHERE Title = %s ORDER BY id DESC LIMIT 1", (title,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertIsNotNone(row)
        task_id, t, desc, created_dt, due_dt = row
        self.created_test_ids.append(task_id)

        self.assertEqual(t, title)
        self.assertEqual(desc, "First line of description\nSecond line of description\nThird line of description")
        self.assertIsNotNone(created_dt)
        self.assertIsNotNone(due_dt)
        print(f"\n[PASS] Test 1: Task with multi-line description added successfully (ID: {task_id}).")

    def test_02_add_task_empty_desc(self):
        """2. Adding a task with an empty description."""
        title = "[TEST] Empty Desc Task"
        inputs = [
            title,
            "",  # Skip due date
            "END"  # Empty description immediately
        ]
        with patch('builtins.input', side_effect=inputs):
            todo.add_tasks()

        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("SELECT id, Title, Description FROM Tasks WHERE Title = %s ORDER BY id DESC LIMIT 1", (title,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertIsNotNone(row)
        task_id, t, desc = row
        self.created_test_ids.append(task_id)

        self.assertEqual(t, title)
        self.assertIsNone(desc)
        print(f"[PASS] Test 2: Task with empty description added successfully (ID: {task_id}).")

    def test_03_view_tasks_null_description(self):
        """3. Viewing tasks when descriptions are NULL."""
        # Insert a dummy row with NULL description
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Description) VALUES (%s, NULL)", ("[TEST] Null Desc Task",))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)
        cursor.close()
        db.close()

        # Capture output of view_tasks to ensure no exception is raised
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            todo.view_tasks()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("[TEST] Null Desc Task", output)
        self.assertIn("(No description)", output)
        print(f"[PASS] Test 3: Viewing tasks with NULL descriptions succeeded without crash.")

    def test_04_edit_title(self):
        """4. Editing a task title."""
        # Create a task to edit
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Description) VALUES (%s, %s)", ("[TEST] Original Title", "Desc"))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)

        # Edit title: task_id, option 1 (Edit Title), 'y', new title, 'n' (don't edit another)
        inputs = [str(task_id), "1", "y", "[TEST] Updated Title", "n"]
        with patch('builtins.input', side_effect=inputs):
            todo.edit_task()

        cursor.execute("SELECT Title FROM Tasks WHERE id = %s", (task_id,))
        new_title = cursor.fetchone()[0]
        cursor.close()
        db.close()

        self.assertEqual(new_title, "[TEST] Updated Title")
        print(f"[PASS] Test 4: Task title edited successfully.")

    def test_05_rewrite_full_description(self):
        """5. Rewriting a full description."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Description) VALUES (%s, %s)", ("[TEST] Rewrite Desc Task", "Old Line 1\nOld Line 2"))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)

        # Edit task -> option 2 (Edit Description) -> option 1 (Rewrite Entire Description) -> lines -> END -> 5 (Exit to Edit Menu) -> 4 (Exit)
        inputs = [
            str(task_id),
            "2",  # Edit Description
            "1",  # Rewrite Entire Description
            "Brand New Line A",
            "Brand New Line B",
            "END",
            "5",  # Back to Edit Menu
            "4",  # Exit edit
            "n"   # No more tasks to edit
        ]
        with patch('builtins.input', side_effect=inputs):
            todo.edit_task()

        cursor.execute("SELECT Description FROM Tasks WHERE id = %s", (task_id,))
        desc = cursor.fetchone()[0]
        cursor.close()
        db.close()

        self.assertEqual(desc, "Brand New Line A\nBrand New Line B")
        print(f"[PASS] Test 5: Full description rewritten successfully.")

    def test_06_edit_delete_insert_lines(self):
        """6. Editing, deleting, and inserting description lines."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Description) VALUES (%s, %s)", ("[TEST] Line Ops Task", "Line 1\nLine 2\nLine 3"))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)

        # 1) Insert a line after line 1:
        # Edit task -> 2 (Edit Desc) -> 4 (Add New Line) -> pos '1' -> 'Line 1.5'
        # 2) Edit line 3 (which is now Line 2) -> 2 (Edit a Line) -> line '3' -> 2 (Rewrite) -> 'Line 2 Revised'
        # 3) Delete line 4 (which is Line 3) -> 2 (Edit a line) -> line '4' -> 1 (Delete)
        # 4) Exit menus
        inputs = [
            str(task_id),
            "2",  # Edit Description
            "4",  # Add New Line
            "1",  # After line 1
            "Line 1.5",
            "2",  # Edit a Line
            "3",  # Line number 3
            "2",  # Rewrite line
            "Line 2 Revised",
            "2",  # Edit a Line
            "4",  # Line number 4
            "1",  # Delete line
            "5",  # Back to edit menu
            "4",  # Exit edit task
            "n"   # No more tasks
        ]
        with patch('builtins.input', side_effect=inputs):
            todo.edit_task()

        cursor.execute("SELECT Description FROM Tasks WHERE id = %s", (task_id,))
        desc = cursor.fetchone()[0]
        cursor.close()
        db.close()

        expected = "Line 1\nLine 1.5\nLine 2 Revised"
        self.assertEqual(desc, expected)
        print(f"[PASS] Test 6: Description lines inserted, edited, and deleted successfully.")

    def test_07_replace_word(self):
        """7. Replacing a word in a description."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Description) VALUES (%s, %s)", ("[TEST] Replace Word Task", "Meeting with Alice at noon"))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)

        inputs = [
            str(task_id),
            "2",  # Edit Description
            "3",  # Replace a word
            "1",  # Line number 1
            "Alice",  # Old word
            "Bob",    # New word
            "5",  # Back
            "4",  # Exit
            "n"   # No more tasks
        ]
        with patch('builtins.input', side_effect=inputs):
            todo.edit_task()

        cursor.execute("SELECT Description FROM Tasks WHERE id = %s", (task_id,))
        desc = cursor.fetchone()[0]
        cursor.close()
        db.close()

        self.assertEqual(desc, "Meeting with Bob at noon")
        print(f"[PASS] Test 7: Word replaced in description successfully.")

    def test_08_search_by_title(self):
        """8. Searching by title."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Description) VALUES (%s, %s)", ("[TEST] UniqueTitleXYZ", "Sample"))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)
        cursor.close()
        db.close()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.input', return_value="UniqueTitleXYZ"):
                todo.search_title()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("UniqueTitleXYZ", output)
        print(f"[PASS] Test 8: Searching by title matched the expected task.")

    def test_09_search_by_status(self):
        """9. Searching for completed and pending tasks."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Completed) VALUES (%s, %s)", ("[TEST] Status Pending Task", 0))
        db.commit()
        id1 = cursor.lastrowid
        self.created_test_ids.append(id1)

        cursor.execute("INSERT INTO Tasks (Title, Completed) VALUES (%s, %s)", ("[TEST] Status Completed Task", 1))
        db.commit()
        id2 = cursor.lastrowid
        self.created_test_ids.append(id2)
        cursor.close()
        db.close()

        # Search pending (0)
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.input', return_value="0"):
                todo.search_status()
            output_pending = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("Status Pending Task", output_pending)
        self.assertNotIn("Status Completed Task", output_pending)

        # Search completed (1)
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.input', return_value="1"):
                todo.search_status()
            output_completed = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("Status Completed Task", output_completed)
        self.assertNotIn("Status Pending Task", output_completed)
        print(f"[PASS] Test 9: Searching by status correctly filters pending and completed tasks.")

    def test_10_mark_completed_and_timestamp(self):
        """10. Marking a task complete and checking its completion timestamp."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title, Completed) VALUES (%s, %s)", ("[TEST] Mark Complete Task", 0))
        db.commit()
        task_id = cursor.lastrowid
        self.created_test_ids.append(task_id)

        # Mark as completed: task_id, '1' (Mark as Completed), 'n' (Don't update another)
        inputs = [str(task_id), "1", "n"]
        with patch('builtins.input', side_effect=inputs):
            todo.mark_change()

        cursor.execute("SELECT Completed, CompletedDT FROM Tasks WHERE id = %s", (task_id,))
        completed, completed_dt = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertEqual(completed, 1)
        self.assertIsNotNone(completed_dt)
        print(f"[PASS] Test 10: Task marked complete and CompletedDT recorded: {completed_dt}.")

    def test_11_delete_task(self):
        """11. Deleting a task."""
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Tasks (Title) VALUES (%s)", ("[TEST] Delete Me Task",))
        db.commit()
        task_id = cursor.lastrowid
        cursor.close()
        db.close()

        inputs = [str(task_id), "y", "n"]  # task_id, confirm 'y', don't delete another 'n'
        with patch('builtins.input', side_effect=inputs):
            todo.del_task()

        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM Tasks WHERE id = %s", (task_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertIsNone(row)
        print(f"[PASS] Test 11: Task {task_id} deleted successfully.")

    def test_12_handling_invalid_inputs(self):
        """12. Handling invalid task IDs, dates, menu choices, and line numbers."""
        # 1) Invalid task ID in edit_task
        inputs_edit = ["abc", "-5", "999999", "cancel"]
        with patch('builtins.input', side_effect=inputs_edit):
            todo.edit_task()  # should handle invalid IDs gracefully without crashing

        # 2) Invalid date in add_tasks
        inputs_add = [
            "[TEST] Invalid Date Task",
            "not-a-date",  # invalid
            "2026/12/31",  # invalid
            "",            # skip
            "END"
        ]
        with patch('builtins.input', side_effect=inputs_add):
            todo.add_tasks()

        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM Tasks WHERE Title = %s", ("[TEST] Invalid Date Task",))
        row = cursor.fetchone()
        if row:
            self.created_test_ids.append(row[0])
        cursor.close()
        db.close()

        # 3) Invalid choices in search_status
        inputs_status = ["invalid", "5"]
        with patch('builtins.input', side_effect=inputs_status):
            todo.search_status()

        # 4) Invalid choices in search_tasks menu
        inputs_search = ["99", "invalid", "3"]
        with patch('builtins.input', side_effect=inputs_search):
            todo.search_tasks()

        print(f"[PASS] Test 12: Invalid task IDs, invalid dates, and invalid menu choices handled safely without crashes.")

    def test_13_persistence_across_sessions(self):
        """13. Restarting the program and confirming saved tasks remain available."""
        # Add task in session 1
        title = "[TEST] Persistence Check Task"
        inputs = [title, "", "Line 1", "Line 2", "END"]
        with patch('builtins.input', side_effect=inputs):
            todo.add_tasks()

        # "Restart" by establishing a brand new connection
        db = todo.get_con()
        cursor = db.cursor()
        cursor.execute("SELECT id, Title, Description, CreatedDT FROM Tasks WHERE Title = %s", (title,))
        row = cursor.fetchone()
        cursor.close()
        db.close()

        self.assertIsNotNone(row)
        task_id = row[0]
        self.created_test_ids.append(task_id)
        self.assertEqual(row[1], title)
        self.assertEqual(row[2], "Line 1\nLine 2")
        self.assertIsNotNone(row[3])
        print(f"[PASS] Test 13: Task persisted across sessions and verified independently in database.")

if __name__ == '__main__':
    unittest.main()
