"""Starter help articles and saved replies (P15). Loaded by migration 0002; `python manage.py load_help_articles` adds any
that are missing (it never overwrites an article the platform owner has edited).

roles: who sees the article ([] = everyone). Body: "## " heading, "- " bullet, "1. " numbered step.
"""
ADMIN, TEACHER, STAFF, PARENT, STUDENT = 'admin', 'teacher', 'staff', 'parent', 'student'
OFFICE = [ADMIN, STAFF]
SCHOOL = [ADMIN, STAFF, TEACHER]
FAMILY = [PARENT, STUDENT]

ARTICLES = [
    # --- getting started ---
    dict(slug='first-steps', module='getting-started', roles=[ADMIN], order=1, title='First steps for a new school',
         summary='The setup checklist, from your school details to your first students.',
         body='''The dashboard shows a setup checklist until everything is done. Work through it in order:

1. Settings → Profile: your school's name, logo, address and contact details.
2. Settings → Language & currency: your country, currency and date format.
3. Academic Setup: the school year and its terms, then classes and sections.
4. Subjects, then staff (Staff → Add), then students (Students → New Student).
5. Fees → Fee Structure: what each class pays, then generate the first invoices.

## Bringing data from another system
Administration → Import data takes spreadsheets for classes, subjects, staff, students and opening balances. Download the template, fill it in, and check the preview: nothing is saved until every row is correct.'''),
    dict(slug='import-data', module='getting-started', roles=[ADMIN], order=2, title='Importing students and staff from a spreadsheet',
         summary='Templates, the preview check and fixing problem rows.',
         body='''1. Administration → Import data, and choose what to import (classes, subjects, staff, students or balances).
2. Download the template: its column names must stay as they are.
3. Fill it in (Excel or CSV) and upload it.
4. The preview lists any problem rows with the reason. Download "problems.csv", fix those rows and upload again.
5. When the preview is clean, press Import. It is all or nothing: either every row is saved or none is.

Import classes and subjects before staff and students, because students are placed in classes by name.'''),
    dict(slug='roles-and-access', module='getting-started', roles=[ADMIN], order=3, title='Who can see and change what',
         summary='Administrators, teachers, office staff, parents and students.',
         body='''- Administrators: the whole school, including fees, reports, settings and security.
- Teachers: their classes: attendance, homework, marks and messages with families. They cannot change fees or school settings.
- Office staff (manager, HR, accountant): the parts of the office their role covers.
- Parents: only their own children: attendance, homework, progress, invoices and messages.
- Students: their own timetable, homework, results and fees.

Security & privacy → People & access lists everyone with access, when they last signed in, and lets you unlock, sign out or switch off an account.'''),

    # --- students ---
    dict(slug='add-student', module='students', roles=OFFICE, order=1, title='Adding a student and their family',
         summary='Admission details, guardians, household and the portal login.',
         body='''1. Students → New Student.
2. Fill in the student's details and class. Required fields are marked.
3. Add the guardians. Brothers and sisters share one household, so fees and messages reach the family once.
4. Save. The student and parent portal logins are created automatically; Students → Portal Logins shows them for the admission letter.

To admit from an online application instead, open Admissions, review the application and press Admit.'''),
    dict(slug='promote-students', module='students', roles=[ADMIN], order=2, title='Moving students up at the end of the year',
         summary='Class promotion, students who leave and the new school year.',
         body='''1. Create the new school year in Academic Setup first.
2. Students → Class Promotion: choose the class, tick who moves up and choose the new class.
3. Students who leave: Students → Active Status, mark them as left with the date and reason. Their records are kept.'''),

    # --- attendance ---
    dict(slug='take-attendance', module='attendance', roles=SCHOOL, order=1, title='Taking attendance',
         summary='Marking the register, late arrivals and corrections.',
         body='''1. Attendance (or Take Attendance on the dashboard), choose the class and date.
2. Everyone starts as present: tap the students who are absent or late.
3. Save. Parents of absent students are told if the school has absence alerts switched on.

A mistake? Open the same class and date again, change it and save. The change is recorded with who made it.'''),
    dict(slug='report-absence', module='attendance', roles=[PARENT], order=2, title='Telling the school your child is absent',
         summary='Reporting an absence from the parent portal.',
         body='''1. Open Attendance in the portal and choose Report an absence.
2. Choose your child, the dates and the reason, and send.
The school sees it straight away, and the day is marked as authorised once the office accepts it.'''),

    # --- fees ---
    dict(slug='fee-structure', module='fees', roles=[ADMIN], order=1, title='Setting up fees and generating invoices',
         summary='Fee structure, discounts, late fees and monthly invoices.',
         body='''1. Settings → Fee Particulars: the kinds of charge (tuition, transport, exams…).
2. Settings → Fee Structure: how much each class pays for each charge.
3. Settings → Discount Type: sibling or scholarship discounts, if any.
4. Fees → Generate Fees Invoice: choose the month and classes. Each student gets an invoice with their discounts.

Late fees are added automatically after the due date if you set a late-fee rule.'''),
    dict(slug='collect-fees', module='fees', roles=OFFICE, order=2, title='Recording a payment and printing a receipt',
         summary='Cash, bank and card payments, and part payments.',
         body='''1. Fees → Collect Fees, find the student.
2. Choose the invoice, enter the amount and how it was paid. Part payments are fine: the rest stays due.
3. Save and print the receipt (Fees Paid Slip).

Card payments made by parents online are recorded automatically once the school has connected Stripe in Fees → Online Payments.'''),
    dict(slug='pay-fees-online', module='fees', roles=FAMILY, order=3, title='Paying fees online',
         summary='Seeing what is due and paying by card.',
         body='''1. Open Fees & Billing in the portal: each invoice shows what is due and by when.
2. Press Pay on an invoice. You are taken to a secure card payment page.
3. After paying you come back to the portal and the invoice shows as paid. A receipt can be downloaded there.

If the Pay button is missing, your school has not switched on online payments: pay at the school office as usual.'''),

    # --- exams ---
    dict(slug='enter-marks', module='exams', roles=SCHOOL, order=1, title='Entering marks and publishing results',
         summary='Exam schedule, marks entry, results and report cards.',
         body='''1. Examination → Exam Schedules: the exam, class, subject and date.
2. Examination → Results Entry: choose the exam and class and type the marks. They save as you go.
3. Result Processing works out totals, grades and positions.
4. Report cards are printed from Gradebook → Report Cards. Families see results in the portal once they are published.'''),

    # --- timetable ---
    dict(slug='timetable', module='timetable', roles=[ADMIN], order=1, title='Building the timetable',
         summary='Periods, teachers and clash checks.',
         body='''1. Academic Setup: set the school day's periods.
2. Timetable → Editor: choose a class and drag subjects into periods, with the teacher and room.
3. Clashes (a teacher or room booked twice) are shown in red and must be fixed before saving.
Teachers and families see their own timetable once it is saved.'''),

    # --- communication ---
    dict(slug='announcements', module='communication', roles=SCHOOL, order=1, title='Sending announcements and messages',
         summary='Announcements to groups, scheduled sending and messages to families.',
         body='''- Announcements: choose who receives it (the whole school, some classes, staff only…). You can schedule it for later.
- Messages: a conversation with one family or colleague. Families reply from the portal.
- Calendar: school events, holidays and exams, shown to everyone it concerns.'''),
    dict(slug='contact-teacher', module='communication', roles=FAMILY, order=2, title="Contacting your child's teacher",
         summary='Messages from the portal.',
         body='''Open Messages in the portal and start a conversation with the teacher or the school office. You get a notification when they reply.
For anything urgent, please phone the school.'''),

    # --- staff ---
    dict(slug='payroll', module='staff', roles=[ADMIN], order=1, title='Running payroll',
         summary='Salaries, payslips and payments.',
         body='''1. Each staff member's salary is set on their profile (Staff → the person → Salary).
2. Salary → Generate Salary: choose the month. Leave and deductions are taken into account.
3. Check the salary sheet, then Pay Salary and print or send the payslips.'''),

    # --- portal ---
    dict(slug='portal-overview', module='portal', roles=FAMILY, order=1, title='Using the parent and student portal',
         summary='What you can see and do in the portal.',
         body='''- My Family (parents): each child's class, timetable and teachers.
- Attendance: each day's attendance, and reporting an absence.
- Assignments: homework, due dates and marks.
- Progress: results and report cards.
- Fees & Billing: invoices, payments and receipts.
- Messages and Announcements: news from the school and conversations with teachers.
- Privacy & consent: your choices, such as photos in school publications.'''),

    # --- account ---
    dict(slug='forgot-password', module='account', roles=[], order=1, title='I forgot my password',
         summary='Resetting your password by email.',
         body='''1. On the sign-in page, choose "Forgot password?".
2. Enter your email address. If it belongs to an account, a link is emailed to you (check your spam folder).
3. The link works once and lets you choose a new password. You are then signed out everywhere else.

No email address on your account (some student logins)? Ask the school office to give you a new password.'''),
    dict(slug='two-step-sign-in', module='account', roles=[], order=2, title='Two-step sign-in with your phone',
         summary='Setting it up, recovery codes and a lost phone.',
         body='''Two-step sign-in asks for a 6-digit code from an app on your phone after your password, so a stolen password alone is not enough.

1. Install an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…).
2. Account settings → My sign-ins & data → Set up two-step sign-in, and scan the QR code.
3. Enter the code the app shows, then save the recovery codes somewhere safe.

## Lost your phone?
On the sign-in page choose "Use a recovery code". Each code works once. No codes left? The school office can reset your two-step sign-in.'''),
    dict(slug='sign-in-security', module='account', roles=[], order=3, title='Keeping your account safe',
         summary='Sign-in history, signing out everywhere and blocked accounts.',
         body='''- Account settings → My sign-ins & data shows when and where your account was used.
- A sign-in you don't recognise? Change your password and press "Sign out everywhere".
- Too many wrong passwords block the account for a few minutes. The school office can unlock it sooner.'''),

    # --- settings ---
    dict(slug='plan-and-billing', module='settings', roles=[ADMIN], order=1, title='Your plan, invoices and paying the subscription',
         summary='Changing plan, invoices and what happens if a payment is late.',
         body='''Settings → Plan & billing shows your plan, what it includes, and your student and staff limits.

- Change plan: the difference for the rest of the period is invoiced straight away.
- Invoices: download them, and pay by card or bank transfer.
- If a renewal is not paid, there are 7 days' grace; after that the school becomes read-only (everything can still be seen and exported, but not changed) until it is paid.'''),
    dict(slug='export-your-data', module='settings', roles=[ADMIN], order=2, title='Exporting all of your school data',
         summary='A full copy in CSV, Excel or JSON.',
         body='''Security & privacy → Data → Export: choose the format. You get an email when the file is ready (it is kept for 7 days).
The export contains every record and uploaded file of your school, with a list of what is included. Passwords and keys are never included.'''),
    dict(slug='privacy-requests', module='settings', roles=[ADMIN], order=3, title='Handling a privacy request',
         summary='When a parent asks to see, correct or delete their data.',
         body='''Requests arrive in Security & privacy → Privacy. Each one shows the deadline (one month by law in many countries).
1. Check who is asking.
2. Do what they asked: download their data, correct it, or delete it.
3. Mark the request as done with a note. The history is kept.'''),

    # --- daily briefs and reports ---
    dict(slug='daily-briefs', module='reports', roles=[ADMIN], order=1, title='Daily briefs: the morning brief and the evening summary',
         summary='One page each morning and evening instead of looking everywhere.',
         body='''Open Daily Briefs in the menu (second item). It has two pages for each school day:

- The morning brief: safety incidents still open, who is out and the lessons that still need cover, student interventions that are overdue, yesterday's attendance, fees overdue, new applications and what is on today's calendar.
- The evening summary: attendance today, incidents, health office visits, cover left unfilled, payments received and what needs doing tomorrow.

Everything on them is a count or an amount for the whole school. No student or staff names appear.

## Draft, then approve
1. Each brief starts as a draft with a short written summary on top. If AI is switched on it is written by AI from the figures; otherwise it is a plain summary of the same figures. The page says which.
2. Read it against the figures, change the words if you like, then press Approve.
3. An approved brief is locked: you can print or delete it, not change it. It records who approved it and when.

## Handy buttons
- Prepare it now (or Prepare again, while it is still a draft) makes it with the latest figures.
- Headlines shows the five figures a principal wants on one screen. Full detail shows every section.
- Mark as read stamps your name and the time so the other administrators can see who has looked.
- Needs attention lists first, with a link to the screen that deals with it.

## Weekly, fortnightly and monthly
The Weekly, fortnightly, monthly tab builds a roll-up from the daily briefs of that period. It is a draft you approve in the same way.

## How long they are kept
Daily briefs and roll-ups are kept for 92 days (about three months). Older ones are removed automatically so they do not pile up. You can print or delete any of them at any time. Times are in your school's time zone and can be changed in the Settings tab.'''),
    dict(slug='planning-reports', module='reports', roles=[ADMIN], order=2, title='Planning: enrolment forecast, score trends and staff signals',
         summary='Reports, then Planning.',
         body='''Reports → Planning has four parts:

- A written read of the figures. Choose a report and press Write the summary. It only describes the numbers, which are shown beside it. It does not explain causes or predict.
- Next year's enrolment: for each grade, this year, expected next year with a low to high range, approved offers, applications waiting, seats left and sections needed. The retention and application-conversion figures it used are shown, and marked "assumed" when your school does not have enough history yet. Set seats for each grade under Admissions.
- Scores term over term, by subject or by class. A drop of 5 points or more is flagged "declining". Groups under 10 students are never shown.
- Staff signals: contracts and probation ending, credentials expiring, a lot of time away, a heavy cover load, a full timetable. These are a prompt for a conversation, not a rating of anyone.'''),
    dict(slug='faq-brief-not-ready', module='reports', kind='faq', roles=[ADMIN], order=10,
         title='Why has my brief not been prepared?', summary='',
         body='Briefs are prepared by a scheduled job at the times in Daily Briefs → Settings, in your school\'s time zone. If the job is not running on your server (for example a free demo server), or Prepare automatically is switched off, press Prepare it now on the Today tab. A figure shown as "not recorded" means nothing was entered, for example attendance that was never marked.'),

    # --- student support, safety and the front office ---
    dict(slug='absence-steps', module='support', roles=[ADMIN], order=1, title='Setting the absence steps',
         summary='What happens as unexcused absences add up.',
         body='''Attendance → Absence Reports has the absence steps. The usual ladder is 3, 5 and 10 unexcused absences in the period.

1. Each step warns the family.
2. A step can also tell staff and open an intervention for the counsellor.
3. Excused absences never count, and each step is sent once until its days have passed.

Add, change or remove steps and press Save ladder. "Back to the usual steps" restores 3, 5 and 10. School Reports → Attendance also shows chronic absenteeism: students who miss 10% or more of the days recorded.'''),
    dict(slug='interventions', module='support', roles=SCHOOL, order=2, title='Interventions: students who need support',
         summary='The counsellor\'s to-do list, with an owner and a due date.',
         body='''Administrators and the counsellor open Interventions in the menu. Teachers and staff see My Interventions: the ones given to them.

An intervention opens by itself when absences reach a step of the absence ladder or the early-warning scan flags a student. You can also add one with New intervention.

## Working on one
1. Open it to see why it opened and some suggested next steps.
2. Give it an owner and a due date (administrators and the counsellor).
3. Add notes as things happen.
4. Press Mark done and say what was done, or Dismiss and say why. Both need a reason.
5. A closed one can be reopened.

The tiles at the top show what is open, overdue and without an owner. An owner can add notes and finish their own interventions but cannot reassign them.'''),
    dict(slug='front-desk-pickup', module='support', roles=OFFICE, order=3, title='Front desk: who may collect a child, and the visitor book',
         summary='Pickup release, do-not-release and visitors.',
         body='''Front Desk is for administrators and the front desk role. It has two tabs.

## Pickup
1. Find the student. You see the parents and guardians who may collect them, and any other authorised adults.
2. Press Release, tick that you checked their photo ID, add a reason if needed, and save.
3. Add someone with Add an authorised adult.

A person marked DO NOT RELEASE (with the court-order note) cannot be released by the front desk. Only an administrator can, by typing a reason that is recorded. Every release is kept and cannot be edited.

## Visitors
Sign visitors in (name, who they visit, purpose, badge number) and out. On site now is the list for an emergency, and Print on-site list prints it.'''),
    dict(slug='health-office', module='support', roles=OFFICE, order=4, title='Health office: visits, medication and immunisations',
         summary='For the school nurse and administrators.',
         body='''Find a student in Health Office, then:

- Visits: New visit records time in and out, the complaint, what was done and whether the student went home. Parents are told automatically.
- Medication: Add medication records what a parent has allowed (medicine, dose, times, dates and the hours that must pass between doses). A dose can only be given against a current permission. If it is too soon after the last one you must type a reason. Doses are never edited afterwards.
- Immunisations have a next due date on the student's Health tab, and parents get one reminder per due date.

Health records are private. Only the nurse, administrators and the child's own parents can see them, and every view is written to the activity log.'''),
    dict(slug='safety-reports', module='support', roles=SCHOOL, order=5, title='Reporting a safety incident',
         summary='Injuries, bullying, damage: who files them and who follows up.',
         body='''Anyone on staff can file a report. Open Safety Reports and press Report an incident: say what happened, where, who was involved, and whether to tell their parents.

- You see the reports you filed.
- Administrators and the counsellor see all of them. They add follow-up tasks with an owner and a due date (overdue ones are flagged at the top) and close the incident with a note.
- A closed incident cannot be changed until it is reopened. Reports are never deleted.'''),
    dict(slug='forms-permission-slips', module='support', roles=[ADMIN], order=6, title='Forms and permission slips',
         summary='Publish a form, see who has signed and remind the rest.',
         body='''Forms → New form: the text families agree to, optional questions (yes/no, short answer, choose one), who it goes to (every family or chosen classes) and a sign-by date.

1. Save it as a draft, then press Publish. Each child's family gets a form to sign and a notification.
2. Who has signed shows signed, declined and waiting. Remind sends a reminder only to those who have not signed.
3. Download the CSV for your records.

A signed form's wording cannot change. Use New version instead.'''),

    # --- AI ---
    dict(slug='ai-drafts', module='ai', roles=[ADMIN, TEACHER], order=1, title='Using AI to draft: lesson plans, family messages and rubrics',
         summary='Drafts for you to read and edit. Nothing is sent or saved for you.',
         body='''Everything the AI writes is a draft. You read it and edit it, and nothing is sent or saved until you do it. The AI never decides grades, admissions or discipline.

## Lesson plans
In the Lesson Planner, open Add Lesson Plan, enter a topic and, if you like, the standards you want addressed (one per line). Generate fills the plan and a standards alignment note for you to edit.

## A message to a family
Messages → New message → Draft with AI. Choose the student, the type (for example a positive note or missing assignments), a tone and write a few notes. It fills the subject and message for you to edit before you press Send. Only the student's first name and your notes are used. If your notes mention health, support plans, discipline or family matters you get a warning: keep those for the office, the nurse or a counsellor.

## A rubric
In the Gradebook, open an assignment and use Rubric → Draft with AI, or type your own. The rubric shows from the column heading while you grade and never changes a score.

## When there is no AI key
The same buttons give a plain template and say so. An administrator can see whether AI is on under AI Assistant in the menu.'''),
    dict(slug='ai-settings', module='ai', roles=[ADMIN], order=2, title='AI Assistant settings: switches, usage and the use notice',
         summary='Turn AI features on or off for your school.',
         body='''Administration → AI Assistant lets you:

- Switch each AI feature on or off for your school.
- See how much AI your school has used this month.
- Accept the AI use notice. Features that use a student's name (such as drafting a message to a family) do not work until an administrator has accepted it.

The notice says what AI is used for and that everything it writes is a draft for staff to check. Whoever runs your server adds the AI provider key; without one the AI features give plain templates and say so.'''),
    dict(slug='translate-and-summarise', module='communication', roles=SCHOOL + FAMILY, order=3, title='Translating and summarising messages',
         summary='Translate a message, and (for staff) a summary with a suggested reply.',
         body='''- Translate: press Translate under a message or an announcement to read it in your language. It is marked as machine translated, and Show original puts the original back. A translation is saved, so the same text is only translated once for each language.
- Summarise (long conversations and announcements): a short summary with the key points.
- For staff, the summary can also include a suggested reply. It goes into your reply box for you to edit and is never sent for you.
- For staff, a message that reads as urgent or upset shows a label in the inbox and sorts to the top. Families never see this label.'''),
    dict(slug='faq-ai-short-answers', module='ai', kind='faq', roles=[ADMIN, TEACHER], order=10,
         title='Why does the assistant give short, keyword-style answers?', summary='',
         body='Your server has no AI provider key, so the assistant answers common questions by matching keywords (the suggested questions work best) and the drafting buttons give plain templates. Ask whoever runs your server to add an OpenAI or Anthropic key. Then the assistant answers in full sentences and suggests natural questions.'),
    dict(slug='faq-no-face-scan', module='attendance', kind='faq', roles=SCHOOL, order=11,
         title='Why is there no face recognition button when I take attendance?', summary='',
         body='The button only appears when your server can actually do face recognition, which needs extra software. If it is not set up the button is hidden rather than showing an error. Mark attendance as usual with the class list.'),
    dict(slug='sign-forms', module='portal', roles=[PARENT], order=2, title='Signing a form or permission slip',
         summary='Forms to Sign.',
         body='''When the school sends a form (for example a permission slip) you get a notification. Open Forms to Sign, read it, answer any questions and type your full name to sign, or decline.

A signed form is final: it keeps the exact wording you agreed to, and the school cannot change it. If the school sends a new version you will be asked to sign again.'''),

    # --- questions and answers ---
    dict(slug='faq-parent-login', module='portal', kind='faq', roles=FAMILY, order=10,
         title='Where do I get my portal login?', summary='',
         body='The school office gives it to you, usually on the admission letter. Your username is your email address (parents) or the student ID (students). If you have lost it, ask the office for a new password, or use "Forgot password?" if your account has an email address.'),
    dict(slug='faq-wrong-class', module='students', kind='faq', roles=OFFICE, order=10,
         title='A student is in the wrong class. How do I move them?', summary='',
         body='Open the student (Students → the name → Edit), change the class and section and save. Their attendance and marks so far stay with them.'),
    dict(slug='faq-read-only', module='settings', kind='faq', roles=[ADMIN], order=10,
         title='Why can we see everything but not change anything?', summary='',
         body="The school's subscription has lapsed after the 7 days' grace, so it is read-only. Pay the open invoice in Settings → Plan & billing and everything works again straight away. Nothing has been deleted."),
    dict(slug='faq-no-email', module='account', kind='faq', roles=[], order=10,
         title="I didn't get the email", summary='',
         body='Check your spam or junk folder and that the address on your account is right. Emails can take a few minutes. Still nothing? Contact the school office (or, for school staff, open a support ticket).'),
]

CANNED = [
    dict(title='Thanks, looking into it', body="Thank you for getting in touch. We're looking into this now and will reply as soon as we know more."),
    dict(title='Need more detail', body='Thanks for the report. Could you tell us which page you were on, what you pressed, and what you expected to happen? A screenshot helps a lot.'),
    dict(title='Fixed, please check', body='This should be fixed now. Could you check on your side and let us know? If everything works, we will close the ticket in a few days.'),
    dict(title='Password reset', body='You can reset a password from the sign-in page with "Forgot password?". For accounts without an email address, the school office can set a new password in Students → Portal Logins or Staff → Portal Logins.'),
    dict(title='Feature request noted', body="Thank you for the idea. We've added it to our list of requests; we can't promise a date, but ideas that many schools ask for come first."),
]
