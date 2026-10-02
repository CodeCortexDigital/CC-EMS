# School data pack: file format

A data pack is a **zip of CSV files**, one file per kind of record. The same files are used to **load** data (Settings > Import data),
to **export** a school, and to **restore** one. This page is generated from the code (`python manage.py pack_spec_doc`), so it is exact.

## Rules for every file

* UTF-8 CSV with a header row (a byte-order mark is fine, so Excel opens it). `.xlsx` is accepted for single files.
* Headings are matched ignoring case, spaces and punctuation, and a trailing `*` is ignored. Alternative headings are listed below.
* Columns marked **required** must have a value. Other columns may be empty.
* Dates are `2026-09-26` (also `26/09/2026`). Times are `08:30`. Yes/no columns accept yes, no, y, n, true, false, 1, 0. Amounts are plain
  numbers (`2500` or `2500.50`; `$` and thousands separators are ignored).
* Records refer to each other by **natural keys people already use**: class name, subject code, student number, employee number,
  invoice number, exam code. Never by internal ids. A reference can only find records of the same school.
* Files load in the order below, so a file can refer to records in the files before it. A file whose references are missing fails
  row by row; the other files still load.
* A file is all-or-nothing: if a row that passed the check cannot be saved, nothing from that file is saved.
* Passwords, tokens and keys are never in a pack. People get new random logins when created.

## Modes

| Mode | What happens to a record that already exists (same key) |
|------|------------------------------------------------------|
| Add only | Left alone. New records are added. |
| Add and update | Updated with the cells you filled in. Empty cells never erase what is there. |
| Restore | Same as update, and only allowed into a school with no students and no staff. |

Every upload is checked first (Preview) and nothing is saved until you press Import. Packs with many rows run in the background.

## Version and manifest

`manifest.json` (written by the exporter, optional on upload) holds `pack_version`, the school name, and for each file its kind, row
count and SHA-256 checksum. A pack with a newer `pack_version` than the system is refused, and a file that does not match its checksum is
refused (delete `manifest.json` to load an edited pack).

## Files

| # | File | What it holds | Needs first |
|---|------|---------------|-------------|
| 1 | `academic_years.csv` | School years | nothing |
| 2 | `terms.csv` | Terms and semesters | academic_years |
| 3 | `classes.csv` | Classes and sections | academic_years |
| 4 | `subjects.csv` | Subjects | nothing |
| 5 | `rooms.csv` | Rooms | nothing |
| 6 | `periods.csv` | Daily periods | academic_years |
| 7 | `weekdays.csv` | School days | nothing |
| 8 | `class_subjects.csv` | Subjects taught in each class | classes, subjects |
| 9 | `pay_grades.csv` | Pay grades | nothing |
| 10 | `staff.csv` | Teachers and staff | subjects |
| 11 | `teacher_assignments.csv` | Teacher assignments | staff, class_subjects |
| 12 | `students.csv` | Students and guardians | classes |
| 13 | `guardians.csv` | Guardians and parents | students |
| 14 | `student_health.csv` | Student health records | students |
| 15 | `immunizations.csv` | Immunisations | students |
| 16 | `admissions.csv` | Admission applications | nothing |
| 17 | `fee_structure.csv` | Fee structure | classes |
| 18 | `invoices.csv` | Invoices | students |
| 19 | `payments.csv` | Payments | invoices |
| 20 | `opening_balances.csv` | Opening fee balances | students |
| 21 | `payroll_profiles.csv` | Staff pay set-up | staff, pay_grades |
| 22 | `payslips.csv` | Salary payslips | staff |
| 23 | `leave_allowances.csv` | Leave allowances | staff |
| 24 | `leave_requests.csv` | Leave requests | staff |
| 25 | `attendance.csv` | Student attendance | students |
| 26 | `staff_attendance.csv` | Staff attendance | staff |
| 27 | `exams.csv` | Exams and tests | classes, subjects |
| 28 | `exam_results.csv` | Exam results | exams, students |
| 29 | `timetable.csv` | Timetable | class_subjects, periods, staff, rooms |
| 30 | `calendar_events.csv` | School calendar | nothing |
| 31 | `contracts.csv` | Staff contracts | staff |
| 32 | `credentials.csv` | Licences and certificates | staff |
| 33 | `reviews.csv` | Performance reviews | staff |
| 34 | `goals.csv` | Staff goals | staff |
| 35 | `job_openings.csv` | Job openings | nothing |
| 36 | `job_candidates.csv` | Job candidates | job_openings |

### `academic_years.csv`: School years

One row per school year, for example 2026-27. Mark the current one with Active = yes.

A record is identified by: School year.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| School year | yes | year |
| Start date | yes |  |
| End date | yes |  |
| Active (yes/no) |  | current, isactive |

Update mode: supported.
Export: yes.

Example row: `2026-27, 2026-08-17, 2027-06-04, yes`

### `terms.csv`: Terms and semesters

Grading periods inside a school year. The school year must already exist.

A record is identified by: School year, Term.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| School year | yes | schoolyear |
| Term | yes |  |
| Type |  | kind |
| Order |  |  |
| Start date | yes |  |
| End date | yes |  |

Update mode: supported.
Export: yes.

Example row: `2026-27, Semester 1, semester, 1, 2026-08-17, 2026-12-18`

### `classes.csv`: Classes and sections

One row per class. List its sections separated by commas (A, B, C).

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Class | yes | classname, grade, class |
| Sections |  | section |
| Grade level |  | level, year |
| Capacity |  | maxstudents, seats |
| Tuition fee |  | fee, monthlyfee |
| Code |  |  |

Update mode: supported.
Export: yes.

Example row: `Grade 1, A, B, 1, 30, 2500, `

### `subjects.csv`: Subjects

One row per subject.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Subject | yes | subjectname |
| Code |  | subjectcode |
| Department |  |  |
| Elective (yes/no) |  | optional, elective |

Update mode: supported.
Export: yes.

Example row: `Mathematics, MATH, Science, no`

### `rooms.csv`: Rooms

Classrooms and special rooms. Category: classroom, lab, sports, hall or other (labs and gyms are used for the matching subjects).

A record is identified by: Room code.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Room code | yes | roomcode |
| Room name | yes | room |
| Capacity |  | seats |
| Category |  | type |
| Floor |  |  |
| Location |  | building |

Update mode: supported.
Export: yes.

Example row: `R101, Room 101, 28, classroom, first, Main building`

### `periods.csv`: Daily periods

The bell schedule for a school year: one row per period, with start and end times.

A record is identified by: School year, Period number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| School year | yes | schoolyear |
| Period number | yes | period |
| Name |  |  |
| Start time | yes |  |
| End time | yes |  |
| Break (yes/no) |  | isbreak, lunch |

Update mode: supported.
Export: yes.

Example row: `2026-27, 1, Period 1, 08:00, 08:45, no`

### `weekdays.csv`: School days

Which days the school is open, and which are half days. Without this file Monday to Friday is used.

A record is identified by: Day.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Day | yes | weekday, name |
| Open (yes/no) |  | isactive |
| Half day (yes/no) |  | half |
| Order |  |  |

Update mode: supported.
Export: yes.

Example row: `Monday, yes, no, 1`

### `class_subjects.csv`: Subjects taught in each class

Which subjects each class takes, and how many periods a week. Both the class and the subject must already exist.

A record is identified by: Class, Subject code.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Class | yes | classname, grade |
| Subject code | yes | subjectcode, code |
| Periods per week |  | periods, lessonsperweek |
| Total marks |  |  |

Update mode: supported.
Export: yes.

Example row: `Grade 5, MATH, 5, 100`

### `pay_grades.csv`: Pay grades

Salary bands for staff, for example Teacher Level 2.

A record is identified by: Pay grade.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Pay grade | yes | grade |
| Monthly base salary | yes | salary |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `Teacher Level 2, 4200, Five or more years`

### `staff.csv`: Teachers and staff

One row per person. Email is required: it becomes their sign-in. Leave the employee number empty to have one made.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Name | yes | name, fullname, teachername |
| Email | yes | emailaddress |
| Phone |  | mobile, phonenumber |
| Employee number |  | employeeid, empid, staffid |
| Role |  | designation, position, jobtitle |
| Department |  |  |
| Subjects |  | specializations, teaches |
| Joining date |  | joined, startdate |
| Gender |  | sex |
| Date of birth |  | dob, birthdate |
| Monthly salary |  | salary |
| Qualifications |  | qualification, degree |
| National ID |  | cnic, nationalid, idnumber |
| Address |  | address |
| Staff type (regular or relief) |  | type, stafftype |
| Manager (employee number) |  | reportsto, managerid, supervisor |

Update mode: supported.
Export: yes.

Example row: `Sara Ahmed, sara@school.edu, 0300 1234567, , Teacher, Science, Physics, Maths, 2026-08-01, Female, , 60000, MSc Physics, , , regular, `

### `teacher_assignments.csv`: Teacher assignments

Which teacher teaches which subject in which class. The teacher must be qualified for the subject (listed in staff.csv) unless you give an override reason.

A record is identified by: Employee number, Class, Subject code, School year.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employee, employeeid, teacher |
| Class | yes | classname, grade |
| Subject code | yes | subjectcode, code |
| School year |  | schoolyear |
| Main teacher (yes/no) |  | isprimary |
| Override reason |  | reason |

Update mode: supported.
Export: yes.

Example row: `EMP-001, Grade 5, MATH, 2026-27, yes, `

### `students.csv`: Students and guardians

One row per student. The class (and section) must exist. Leave the student number empty to continue your numbering. Guardians' details create the family and the parent's portal login, as on the admission form.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Name | yes | name, studentname, fullname |
| Class | yes | classname, grade |
| Section |  |  |
| Student number |  | studentid, rollno, registrationno, admissionno, grno |
| Gender |  | sex |
| Date of birth |  | dob, birthdate |
| Admission date |  | admitted, joiningdate |
| Student email |  | email |
| Student phone |  | phone, mobile |
| Father name |  | father, fathersname |
| Mother name |  | mother, mothersname |
| Guardian name |  | guardian |
| Guardian phone |  | parentphone, fatherphone, fathermobile, contact |
| Address |  | homeaddress |
| City |  | town |
| Religion |  |  |
| Blood group |  | bloodgroup |
| Birth certificate / B-Form |  | bform, birthcertificate |
| Previous school |  |  |
| Family (siblings share the name) |  | familyname, household, selectfamily |

Update mode: supported.
Export: yes.

Example row: `Ali Raza, Grade 1, A, , Male, 2019-04-12, , , , Raza Khan, Amna Raza, , 0300 7654321, 12 Park Road, Lahore, , , , , Raza family`

### `guardians.csv`: Guardians and parents

One row per guardian per student: name, relationship, contact details, and what they may do (collect the child, receive bills...). Parents named on the student file already exist; matching names are updated in update mode.

A record is identified by: Student number, First name, Last name.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Student number | yes | studentid, studentno, admissionno |
| First name | yes | firstname, guardianfirstname |
| Last name |  | lastname, surname |
| Relationship | yes |  |
| Email |  |  |
| Mobile phone |  | mobile, phone |
| Home phone |  |  |
| Work phone |  |  |
| Occupation |  |  |
| Employer |  |  |
| Address |  |  |
| Primary contact (yes/no) |  | primary |
| Lives with student (yes/no) |  |  |
| Has custody (yes/no) |  | custody |
| May collect (yes/no) |  | pickup |
| Emergency contact (yes/no) |  | emergency |
| Receives bills (yes/no) |  | billing |
| Receives messages (yes/no) |  | messages |
| Portal access (yes/no) |  | portal |
| Contact order |  |  |

Update mode: supported.
Export: yes.

Example row: `DS-2026001, Amna, Raza, mother, amna@example.com, 0300 7654321, , , Nurse, City Hospital, 12 Park Road, yes, yes, yes, yes, yes, yes, yes, yes, 1`

### `student_health.csv`: Student health records

Allergies, conditions, medication, doctor and insurance. One row per student.

A record is identified by: Student number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Student number | yes | studentid, studentno |
| Allergies |  |  |
| Severe allergy (yes/no) |  | epipen, severe |
| Medical conditions |  | conditions |
| Medications |  | medication |
| Dietary restrictions |  | diet |
| Doctor |  | physician, doctorname |
| Doctor phone |  | doctorphone |
| Insurance provider |  | insurance |
| Insurance policy number |  | policynumber |
| Emergency treatment consent (yes/no) |  | consent |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `DS-2026001, Peanuts, yes, Asthma, Inhaler as needed, , Dr. Lee, 555-0100, BlueCross, BC-123456, yes, `

### `immunizations.csv`: Immunisations

One row per vaccine dose per student. Mark exemptions with Exempt = yes and a reason.

A record is identified by: Student number, Vaccine, Dose.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Student number | yes | studentid, studentno |
| Vaccine | yes |  |
| Dose |  |  |
| Date given |  |  |
| Exempt (yes/no) |  |  |
| Exemption reason |  |  |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `DS-2026001, MMR, 1, 2020-03-14, no, , `

### `admissions.csv`: Admission applications

Applications to the school and where each one stands. Leave the application number empty for new applications; a number is made for you. Admitted children join the student list through the Admissions screen.

A record is identified by: Application number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Application number |  | applicationno, appno |
| Applicant name | yes | name, applicant, studentname |
| Email | yes | emailaddress |
| Phone |  | mobile |
| Date of birth |  | dob |
| Gender |  |  |
| Applying for class | yes | class, grade, applyingfor |
| Section |  |  |
| School year |  | year |
| Status |  |  |
| Programme |  | program |
| Notes |  | notes |
| Father name |  |  |
| Father phone |  |  |
| Mother name |  |  |
| Mother phone |  |  |
| Guardian name |  |  |
| Guardian phone |  |  |
| Previous school |  |  |
| Address |  |  |
| City |  |  |

Update mode: supported.
Export: yes.

Example row: `, Noah Miller, noah.miller@example.com, 555-0142, 2020-05-02, male, Kindergarten, , 2026-2027, pending, , , Emma Miller, 555-0142, , , , , , 12 Oak Street, Springfield`

### `fee_structure.csv`: Fee structure

The fees each class is charged: name, amount, due date and how often. The class must already exist.

A record is identified by: Class, Section, Fee, School year.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Class | yes | classname, grade |
| Section |  |  |
| Fee | yes | name, feename |
| Amount | yes |  |
| Due date | yes |  |
| School year |  | year |
| Recurring (yes/no) |  |  |
| Frequency |  |  |

Update mode: supported.
Export: yes.

Example row: `Grade 5, , Tuition, 2500, 2026-09-10, 2026-27, yes, monthly`

### `invoices.csv`: Invoices

Fee invoices already issued. What was paid comes from the payments file, so import payments after invoices. Families are not notified when invoices are loaded this way.

A record is identified by: Invoice number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Invoice number | yes | invoiceno, number |
| Student number | yes | studentid, studentno |
| Type |  | type |
| Amount | yes |  |
| Balance brought forward |  |  |
| Discount |  | discount |
| Late fee |  | latefee |
| Due date | yes |  |
| Issue date |  |  |
| Invoice month |  | month |
| Status |  |  |
| Description |  | details |

Update mode: supported.
Export: yes.

Example row: `INV-2026-09-0001, DS-2026001, tuition, 2500, 0, 0, 0, 2026-09-10, 2026-09-01, 2026-09-01, issued, September fees`

### `payments.csv`: Payments

Money received against invoices. Each payment needs the invoice number, the amount and a reference (receipt or transaction number). A payment cannot be more than the invoice still owes.

A record is identified by: Invoice number, Receipt reference.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Invoice number | yes | invoiceno |
| Receipt reference |  | receipt, transactionid, receiptno |
| Amount | yes |  |
| Date paid |  |  |
| Method |  | method |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `INV-2026-09-0001, RCPT-1001, 2500, 2026-09-05, bank_transfer, `

### `opening_balances.csv`: Opening fee balances

What each family still owes from before. One row per student; import students first.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Student number | yes | studentid, rollno, registrationno, admissionno |
| Amount owed | yes | amount, balance, due, arrears |
| Due date |  | duedate |
| Note |  | description, details |

Update mode: not supported (existing records are left alone).
Export: yes.

Example row: `DS-2026001, 4500, 2026-10-10, Fees Jan–Aug 2026`

### `payroll_profiles.csv`: Staff pay set-up

Each person's pay grade, tax withholding percentage and benefits. Benefits look like Transport:200:allowance; Health plan:100:deduction.

A record is identified by: Employee number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Pay grade |  | grade |
| Tax withheld % |  | tax, taxrate |
| Benefits |  |  |

Update mode: supported.
Export: yes.

Example row: `EMP-001, Teacher Level 2, 10, Transport:200:allowance; Health plan:100:deduction`

### `payslips.csv`: Salary payslips

Monthly salary records. Net pay is worked out for you: basic + allowances - deductions.

A record is identified by: Employee number, Month (first day).

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Month (first day) | yes |  |
| Basic salary | yes | basic |
| Allowances |  |  |
| Deductions |  |  |
| Paid so far |  | paid |
| Date paid |  |  |
| Payment method |  |  |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `EMP-001, 2026-09-01, 4200, 200, 420, 0, , , `

### `leave_allowances.csv`: Leave allowances

How many days of each kind of leave a person has per year, plus any days carried over from last year.

A record is identified by: Employee number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Sick days |  |  |
| Casual days |  |  |
| Annual days |  |  |
| Personal days |  |  |
| Bereavement days |  |  |
| Jury duty days |  |  |
| Professional development days |  |  |
| Maternity days |  |  |
| Emergency days |  |  |
| Other days |  |  |
| Carried over days |  |  |

Update mode: supported.
Export: yes.

Example row: `EMP-001, 5, 5, 15, 3, 3, , , , , , 2`

### `leave_requests.csv`: Leave requests

Leave taken or booked. Loading approved leave records it only; it does not arrange substitute cover.

A record is identified by: Employee number, First day, Last day.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Type | yes | type |
| First day | yes | start |
| Last day | yes | end |
| Day part |  |  |
| Status |  |  |
| Reason |  |  |

Update mode: supported.
Export: yes.

Example row: `EMP-001, sick, 2026-10-05, 2026-10-06, full, approved, Flu`

### `attendance.csv`: Student attendance

One row per student per day. Loading history does not send absence alerts to families.

A record is identified by: Student number, Date.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Student number | yes | studentid, studentno |
| Date | yes |  |
| Status | yes |  |
| Reason |  |  |
| Excused (yes/no) |  |  |
| Minutes late |  |  |
| Remarks |  |  |

Update mode: supported.
Export: yes.

Example row: `S-0001, 2026-09-08, present, , no, , `

### `staff_attendance.csv`: Staff attendance

One row per staff member per day.

A record is identified by: Employee number, Date.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid |
| Date | yes |  |
| Status | yes |  |
| Reason |  |  |

Update mode: supported.
Export: yes.

Example row: `T-001, 2026-09-08, present, `

### `exams.csv`: Exams and tests

Exams, tests and quizzes. Leave the exam code empty for new ones; a code is made. Results go in exam_results.csv, using the exam code.

A record is identified by: Exam code.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Exam code |  | code |
| Title | yes |  |
| Type | yes | type |
| Class | yes | classname, grade |
| Section |  |  |
| Subject code | yes | subjectcode |
| Total marks | yes |  |
| Passing marks | yes |  |
| Exam date | yes | date |
| Start time |  |  |
| End time |  |  |
| Minutes |  |  |
| School year |  | year |
| Term |  |  |
| Published (yes/no) |  |  |
| Active (yes/no) |  |  |

Update mode: supported.
Export: yes.

Example row: `, Unit 1 test, test, Grade 5, , MATH, 50, 25, 2026-09-30, , , , 2026-27, first, yes, yes`

### `exam_results.csv`: Exam results

Marks per student per exam. The grade and percentage are worked out. Families are not notified when results are loaded this way.

A record is identified by: Exam code, Student number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Exam code | yes | examcode, code |
| Student number | yes | studentid, studentno |
| Marks | yes | obtained, score |
| Remarks |  |  |

Update mode: supported.
Export: yes.

Example row: `EXM-2026-0001, S-0001, 44, `

### `timetable.csv`: Timetable

One row per lesson: school year, class, section, day, period, subject, teacher and room. Teachers must be qualified for the subject, and nobody (teacher, room or class) can be in two places in one period.

A record is identified by: School year, Class, Section, Day, Period number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| School year | yes | schoolyear |
| Class | yes | classname, grade |
| Section |  |  |
| Day | yes | weekday |
| Period number | yes | periodnumber |
| Subject code | yes | subjectcode |
| Employee number | yes | employee, employeeid |
| Room code | yes | roomcode, classroom |

Update mode: supported.
Export: yes.

Example row: `2026-27, Grade 5, A, Monday, 1, MATH, T-001, R101`

### `calendar_events.csv`: School calendar

Holidays, closures, trips and meetings. Holidays and closures are not counted against leave and need no attendance.

A record is identified by: Title, First day.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Title | yes |  |
| Type |  | type |
| First day | yes | start |
| Last day | yes | end |
| Location |  |  |
| For |  |  |
| School closed (yes/no) |  | closed |
| Description |  |  |

Update mode: supported.
Export: yes.

Example row: `Fall break, holiday, 2026-10-12, 2026-10-12, , everyone, yes, No school`

### `contracts.csv`: Staff contracts

Employment contracts, with the end date and probation end used for expiry alerts.

A record is identified by: Employee number, Starts.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Type |  | type |
| Starts | yes |  |
| Ends |  |  |
| Probation ends |  |  |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `T-001, full_time, 2024-08-01, , 2025-02-01, `

### `credentials.csv`: Licences and certificates

Teaching licences, first aid, background checks. Expiry dates drive the alerts.

A record is identified by: Employee number, Credential, Number.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Credential | yes |  |
| Issued by |  |  |
| Number |  |  |
| Issued on |  |  |
| Expires on |  |  |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `T-001, State teaching licence, State Board, TL-4471, 2023-07-01, 2028-06-30, `

### `reviews.csv`: Performance reviews

Reviews and observations. Drafts stay private to HR until shared.

A record is identified by: Employee number, Type, Period, Date.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Type |  | type |
| Period |  |  |
| Date | yes |  |
| Rating (1-5) |  |  |
| Strengths |  |  |
| Areas to improve |  |  |
| Lesson observed |  |  |
| Status |  |  |
| Employee comment |  |  |

Update mode: supported.
Export: yes.

Example row: `T-001, annual, 2025-26, 2026-06-10, 4, Great rapport with students, Use more group work, , shared, `

### `goals.csv`: Staff goals

Professional goals and how far along they are.

A record is identified by: Employee number, Goal.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Employee number | yes | employeeid, staff |
| Goal | yes |  |
| Details |  |  |
| Due |  |  |
| Progress % |  |  |
| Status |  |  |

Update mode: supported.
Export: yes.

Example row: `T-001, Run a maths club, Weekly after school, 2027-03-01, 40, open`

### `job_openings.csv`: Job openings

Positions the school is hiring for.

A record is identified by: Job title.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Job title | yes |  |
| Department |  |  |
| Positions |  |  |
| Status |  |  |
| Closes on |  |  |
| Description |  |  |

Update mode: supported.
Export: yes.

Example row: `Science teacher, Science, 1, open, 2026-11-30, Grades 6 to 8`

### `job_candidates.csv`: Job candidates

People who applied for an opening and where they stand. Hiring is done in the Recruitment screen.

A record is identified by: Job title, Name, Email.

| Column | Required | Also accepted as |
|--------|----------|------------------|
| Job title | yes | job, position |
| Name | yes | candidate |
| Email |  |  |
| Phone |  |  |
| Source |  |  |
| Stage |  |  |
| Rating (1-5) |  |  |
| Notes |  |  |

Update mode: supported.
Export: yes.

Example row: `Science teacher, Dana Rivers, dana@example.com, 555-0177, Website, interview, 4, `
