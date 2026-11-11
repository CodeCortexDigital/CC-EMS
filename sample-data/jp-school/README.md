# みどり市立 若葉学園 (Wakaba Gakuen): sample Japanese school (grades 1-9)

A complete, invented public nine-year school as a CC-EMS data pack: 109 students in nine grades (1年 to 9年), 27 staff,
a clash-free timetable (six lessons a day, with 給食 and 中休み), school lunch fees and payments in yen, attendance, exams, payroll, leave,
admissions for the next school year, health records and a Japanese school calendar (national holidays, 運動会, 個人面談). The school year
is April to March in three terms (1学期, 2学期, 3学期). Names are written family name first. Names and numbers are made up. Loaded up to 6 November 2026.

## Use it

* **In the app:** Settings > Import data > Load data, choose `jp-school-pack.zip`, pick **Add and update**, check the preview, Import.
* **From the command line:** `python manage.py load_pack ../sample-data/jp-school --school "Wakaba Gakuen"`

## Files (loaded in this order)

1. `academic_years.csv`: School years (1 rows)
2. `terms.csv`: Terms and semesters (3 rows)
3. `classes.csv`: Classes and sections (9 rows)
4. `subjects.csv`: Subjects (12 rows)
5. `rooms.csv`: Rooms (18 rows)
6. `periods.csv`: Daily periods (8 rows)
7. `weekdays.csv`: School days (5 rows)
8. `class_subjects.csv`: Subjects taught in each class (87 rows)
9. `pay_grades.csv`: Pay grades (5 rows)
10. `staff.csv`: Teachers and staff (27 rows)
11. `teacher_assignments.csv`: Teacher assignments (87 rows)
12. `students.csv`: Students and guardians (109 rows)
13. `guardians.csv`: Guardians and parents (218 rows)
14. `student_health.csv`: Student health records (109 rows)
15. `admissions.csv`: Admission applications (20 rows)
16. `fee_structure.csv`: Fee structure (18 rows)
17. `invoices.csv`: Invoices (218 rows)
18. `payments.csv`: Payments (198 rows)
19. `opening_balances.csv`: Opening fee balances (5 rows)
20. `payroll_profiles.csv`: Staff pay set-up (27 rows)
21. `payslips.csv`: Salary payslips (54 rows)
22. `leave_allowances.csv`: Leave allowances (27 rows)
23. `leave_requests.csv`: Leave requests (6 rows)
24. `attendance.csv`: Student attendance (2180 rows)
25. `staff_attendance.csv`: Staff attendance (324 rows)
26. `exams.csv`: Exams and tests (18 rows)
27. `exam_results.csv`: Exam results (218 rows)
28. `timetable.csv`: Timetable (296 rows)
29. `calendar_events.csv`: School calendar (18 rows)
30. `behaviour_categories.csv`: Behaviour categories (8 rows)
31. `behaviour_incidents.csv`: Behaviour log (100 rows)
32. `observations.csv`: Counselling and meeting notes (12 rows)

Rebuild with `python manage.py build_sample_pack --pack jp --out ../sample-data/jp-school`.
