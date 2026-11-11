# Maple Grove Academy: sample US school (K-8)

A complete, invented private school as a CC-EMS data pack: 83 students in nine classes (Kindergarten to Grade 8),
24 staff, a clash-free timetable, three months of fees and payments, attendance, exams, payroll, leave, admissions
applications, health records, HR records and the school calendar. Names and numbers are made up. Dates are school year 2026-27,
loaded up to 2 October 2026.

## Use it

* **In the app:** Settings > Import data > Load data, choose `us-school-pack.zip`, pick **Add and update**, check the preview, Import.
  Use **Restore** on a brand new, empty school.
* **From the command line:** `python manage.py load_pack ../sample-data/us-school --school "Maple Grove Academy"`
* **Demo school with logins:** `python manage.py seed_demo --pack us-school`

## Files (loaded in this order)

1. `academic_years.csv`: School years (1 rows)
2. `terms.csv`: Terms and semesters (2 rows)
3. `classes.csv`: Classes and sections (9 rows)
4. `subjects.csv`: Subjects (9 rows)
5. `rooms.csv`: Rooms (15 rows)
6. `periods.csv`: Daily periods (9 rows)
7. `weekdays.csv`: School days (5 rows)
8. `class_subjects.csv`: Subjects taught in each class (72 rows)
9. `pay_grades.csv`: Pay grades (5 rows)
10. `staff.csv`: Teachers and staff (24 rows)
11. `teacher_assignments.csv`: Teacher assignments (72 rows)
12. `students.csv`: Students and guardians (83 rows)
13. `guardians.csv`: Guardians and parents (166 rows)
14. `student_health.csv`: Student health records (83 rows)
15. `immunizations.csv`: Immunisations (249 rows)
16. `admissions.csv`: Admission applications (28 rows)
17. `fee_structure.csv`: Fee structure (18 rows)
18. `invoices.csv`: Invoices (166 rows)
19. `payments.csv`: Payments (150 rows)
20. `opening_balances.csv`: Opening fee balances (6 rows)
21. `payroll_profiles.csv`: Staff pay set-up (24 rows)
22. `payslips.csv`: Salary payslips (48 rows)
23. `leave_allowances.csv`: Leave allowances (24 rows)
24. `leave_requests.csv`: Leave requests (6 rows)
25. `attendance.csv`: Student attendance (1660 rows)
26. `staff_attendance.csv`: Staff attendance (288 rows)
27. `exams.csv`: Exams and tests (18 rows)
28. `exam_results.csv`: Exam results (166 rows)
29. `timetable.csv`: Timetable (260 rows)
30. `calendar_events.csv`: School calendar (13 rows)
31. `contracts.csv`: Staff contracts (24 rows)
32. `credentials.csv`: Licences and certificates (17 rows)
33. `reviews.csv`: Performance reviews (8 rows)
34. `goals.csv`: Staff goals (8 rows)
35. `job_openings.csv`: Job openings (2 rows)
36. `job_candidates.csv`: Job candidates (6 rows)
37. `behaviour_categories.csv`: Behaviour categories (10 rows)
38. `behaviour_incidents.csv`: Behaviour log (174 rows)
39. `skills.csv`: Skills to rate (8 rows)
40. `behaviour_ratings.csv`: Skill ratings (166 rows)
41. `observations.csv`: Counselling and meeting notes (16 rows)

All files are plain CSV (UTF-8). People refer to each other by student number (`MG26-001`), employee number (`E-001`),
class name, subject code and invoice number, never by internal ids.

Rebuild with `python manage.py build_sample_pack` (same seed gives the same files).
