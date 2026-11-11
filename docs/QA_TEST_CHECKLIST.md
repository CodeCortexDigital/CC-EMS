# CC-EMS: QA Test Checklist

For: the Quality team. Tick each box when the **Expected** result is seen. If it is not, write the ID, the page address, the login used and a screenshot in the defect log (section 20).

| Result | Meaning |
|---|---|
| ✅ | Pass |
| ❌ | Fail: log a defect |
| ⛔ | Blocked: could not test, say why |
| N/A | Not applicable to this build |

---

## 0. Test set-up

**Build / date / tester / browser / screen size:** ______________________________

**Start the demo:** double-click `demo.bat` (first run loads *Maple Grove Academy*). App: http://localhost:5179 · API: port 8009. To stop: `stop-demo.bat`. To start clean: `restart-demo.bat`.

**Demo logins**

| Role | Email | Password |
|---|---|---|
| Admin | admin@code.com | Admin@123 |
| Deputy admin | deputy@code.com | Deputy@123 |
| Teacher (maths, Grade 6) | teacher@code.com | Teacher@123 |
| Parent (two children) | parent@code.com | Parent@123 |
| Student (Grade 8) | student@code.com | Student@123 |

**Browsers to cover:** Chrome, Edge, Firefox (latest), plus Safari/iPhone and Android Chrome for section 18.
**Screen widths:** 1920, 1440, 1280, 1100 (desktop menu); 768 and 390 (tablet/phone).

**Without API keys** the AI assistant runs in *quick-answer mode*; AI drafts give a standard template and say so. The risk scan and face attendance may be switched off on the hosted demo (they say so). Mark these N/A, not Fail.

---

## 1. Automated checks (run first, by a developer or QA with a terminal)

| ID | Check | Expected | Result |
|---|---|---|---|
| 1.1 | `cd backend` → `set USE_SQLITE=1` → `pytest` | All pass, no errors | ☐ |
| 1.2 | `cd frontend` → `npm run test` | All pass | ☐ |
| 1.3 | `cd frontend` → `npx tsc -p tsconfig.app.json --noEmit` | No errors in app files | ☐ |
| 1.4 | `cd frontend` → `npm run build` | Build finishes, no errors | ☐ |
| 1.5 | `python manage.py migrate` on a fresh database | Finishes with no errors | ☐ |
| 1.6 | Open API docs (`/api/docs`, Swagger/Redoc) | Page loads, endpoints listed | ☐ |

---

## 2. Sign-in, account and session

| ID | Test | Expected | Result |
|---|---|---|---|
| 2.1 | Open the sign-in page | Greeting by the hour, "What you get" card on wide screens, three-way switch (Admin / Staff / Student and Parent), light/dark switch | ☐ |
| 2.2 | Sign in with each of the five demo logins | Each lands on its own home page, no error | ☐ |
| 2.3 | Wrong password | Clear error, no sign-in, no details leaked about whether the email exists | ☐ |
| 2.4 | Empty email / empty password | Field messages shown | ☐ |
| 2.5 | Many wrong passwords in a row | Locked or slowed down with a message | ☐ |
| 2.6 | Light/dark switch on the sign-in page | Theme carries into the app after sign-in | ☐ |
| 2.7 | Forgot password → enter email → open email link → set new password | New password works, old one does not | ☐ |
| 2.8 | Reset link used twice or expired | Refused with a clear message | ☐ |
| 2.9 | Verify-email page | Works for a valid link, clear message for a bad one | ☐ |
| 2.10 | Log out (from the account menu) | Returns to sign-in; the Back button does not show private pages | ☐ |
| 2.11 | Leave the app idle until the session ends | Asked to sign in again, no data loss on the sign-in screen | ☐ |
| 2.12 | Open a private page address while signed out | Redirected to sign-in, then returned to that page after login | ☐ |
| 2.13 | Two roles signed in, two browsers | Each sees only its own data | ☐ |
| 2.14 | Google / Microsoft sign-in buttons | Start the sign-in, or are hidden when not set up (no broken button) | ☐ |
| 2.15 | Create your school (`/signup`) with a password | New school created, signed in as its administrator, empty dashboard with setup checklist | ☐ |
| 2.16 | Create your school with Google | Same as 2.15 | ☐ |
| 2.17 | Sign up with a school name already used | Handled with a clear message | ☐ |
| 2.18 | Change own password (Settings → Account) | Works; old password rejected afterwards | ☐ |
| 2.19 | Portal login letter after the person changes their own password | Letter shows "Changed by user" | ☐ |
| 2.20 | Guided tour at every sign-in until all steps finished | Tour appears; **Skip** hides it for that sign-in only; it returns next sign-in until finished | ☐ |

---

## 3. Top menu (desktop) and navigation: every role

Do these at 1920, 1440, 1280 and 1100 px wide, as **admin** first.

| ID | Test | Expected | Result |
|---|---|---|---|
| 3.1 | Look at the bar | Dark teal gradient, text-only tabs (no icons), tabs centred in the whole bar, all on one line | ☐ |
| 3.2 | Right side of the bar | Favourites star and a switch-to-sidebar button | ☐ |
| 3.3 | Dashboard tab | Shows as "Home" | ☐ |
| 3.4 | Narrow the window from 1920 to 1100 | Tabs never wrap or overlap; those that do not fit go under **More** | ☐ |
| 3.5 | Point at a tab (do not click) | Panel opens **at once**, full width under the bar, 280 px high | ☐ |
| 3.6 | Panel colour | Solid colour for that module, white text everywhere; open tab has the same colour with a small triangle under it | ☐ |
| 3.7 | Panel parts | Left: darker tile with big thin icon and module name in capitals. Middle: slightly darker **About** box (label, one sentence, outlined **OPEN** button). Right: links in two columns (three on very wide screens) | ☐ |
| 3.8 | Every module has a different colour | Home, People, Teaching, Academics, Billing, Comms, Services, Reports, Admin, Settings all clear and readable | ☐ |
| 3.9 | Links | Small `>` arrow, wide letter-spacing, soft white text | ☐ |
| 3.10 | Point at one link | **Only that link** turns full white; no background change | ☐ |
| 3.11 | Current page in the panel | Bold white on a faint white tint | ☐ |
| 3.12 | Slide from tab to tab along the bar | Panels switch at once, no flicker or blank gap | ☐ |
| 3.13 | Move from a tab down into the panel to a far link | Panel does **not** close on the way (gap strip works) | ☐ |
| 3.14 | Move the pointer off the bar and panel | Panel closes at once | ☐ |
| 3.15 | With a panel open, move over the Sidebar button or empty bar space | Panel closes | ☐ |
| 3.16 | Esc with a panel open | Closes | ☐ |
| 3.17 | Click outside with a panel open | Closes | ☐ |
| 3.18 | Click a link in the panel | Goes to that page and the panel closes | ☐ |
| 3.19 | Mouse click on a tab | Goes to that module's first page | ☐ |
| 3.20 | **OPEN** button in the About box | Goes to the module's first page | ☐ |
| 3.21 | Touch screen: tap a tab | First tap only opens the panel; tapping again or a link goes | ☐ |
| 3.22 | More tab | Opens a panel listing the hidden modules and their pages, white text on solid colour | ☐ |
| 3.23 | Favourites: star beside a link | Added to Favourites; star filled | ☐ |
| 3.24 | Favourites panel | Lists starred pages; click goes to the page | ☐ |
| 3.25 | Star a ninth page | Message that favourites are full; list stays at 8 | ☐ |
| 3.26 | Un-star a page | Removed from Favourites | ☐ |
| 3.27 | Reload the page | Favourites and menu choice are kept | ☐ |
| 3.28 | Keyboard: Tab key through the bar and panel | Reaches tabs and links in order, visible focus; Enter opens a page | ☐ |
| 3.29 | Switch to sidebar and back | Both menus work; choice is remembered | ☐ |
| 3.30 | Settings tab | Panel lists every settings section (Profile, Theme, Language & currency, Account, Plan & billing, Help…). **Security & privacy** is not here, it is under Admin | ☐ |
| 3.31 | Admin tab | Security & privacy, Import data, Integrations, AI, All Schools (the last only for platform admins) | ☐ |
| 3.32 | **Every page reachable:** open every link in every panel for the admin | Each opens a page (no blank page, 404 or console error). Record any broken link | ☐ |
| 3.33 | Browser console while using the menu | No errors | ☐ |
| 3.34 | Page scroll sideways | None at any width | ☐ |
| 3.35 | Font in panels | Raleway if installed, otherwise Segoe UI; no layout jump | ☐ |
| 3.36 | **Student and parent** logins | Keep the compact side menu, not the top bar | ☐ |
| 3.37 | **Teacher** login | Top menu shows only teaching tabs and pages they may use | ☐ |

---

## 4. Roles and permissions (cross-check)

For each role, try the page directly by typing its address, not only from the menu.

| ID | Test | Expected | Result |
|---|---|---|---|
| 4.1 | Student opens an admin page (e.g. `/education/fees`, `/admin/audit-logs`) | Refused / redirected, no data shown | ☐ |
| 4.2 | Parent opens another family's student page | Refused; no data | ☐ |
| 4.3 | Teacher opens finance pages | Refused | ☐ |
| 4.4 | Teacher sees only their classes in attendance, gradebook, homework | Yes | ☐ |
| 4.5 | Parent sees only their own two children | Yes | ☐ |
| 4.6 | Student sees only own timetable, homework, results | Yes | ☐ |
| 4.7 | Menu hides pages the role cannot use | Yes, and a hidden page's address still refuses | ☐ |
| 4.8 | Report cards, transcripts, grades, receipts, invoice PDFs | A family or student can download only their own; school-wide finance PDFs only for finance staff | ☐ |
| 4.9 | Analytics page lists only students the login may see | Yes | ☐ |
| 4.10 | API called without a token | 401 | ☐ |
| 4.11 | API called with another role's token on a restricted endpoint | 403 | ☐ |

---

## 5. Multi-school isolation (cross-check, important)

Create (or use) two schools: Maple Grove Academy and a second one made with Create your school.

| ID | Test | Expected | Result |
|---|---|---|---|
| 5.1 | Second school's admin searches for students, staff, families, invoices | Sees nothing from Maple Grove | ☐ |
| 5.2 | Change a student's ID in the address bar to one from the other school | Not found / refused | ☐ |
| 5.3 | Student and staff IDs | Carry a per-school prefix; no clash across schools | ☐ |
| 5.4 | Dashboard, reports and exports of school B | Contain only B's data | ☐ |
| 5.5 | AI assistant of school B asked about school A | No data from A | ☐ |
| 5.6 | Audit log of each school | Only its own events | ☐ |
| 5.7 | Parent with children in two schools | Opens one school only, never mixes both | ☐ |
| 5.8 | Per-student data copy and erasure | Copy contains only that student; erase removes only that student | ☐ |

---

## 6. Dashboard and brief

| ID | Test | Expected | Result |
|---|---|---|---|
| 6.1 | Admin dashboard | Loads with numbers, no spinner stuck, no console error | ☐ |
| 6.2 | New empty school | Setup checklist (profile, classes, subjects, staff, students, fees); ticks as each is done | ☐ |
| 6.3 | Daily brief | **Prepare it now** makes a brief; shows what needs approval | ☐ |
| 6.4 | Numbers match the lists (students, staff, fees due) | Equal | ☐ |
| 6.5 | Teacher, parent, student dashboards | Each shows its own content | ☐ |
| 6.6 | "Sample data" bar | Shown on the demo build | ☐ |

---

## 7. Students and families

| ID | Test | Expected | Result |
|---|---|---|---|
| 7.1 | Students list: search, filter, sort, page | Works; count correct (83 in the demo) | ☐ |
| 7.2 | Add student (all required fields) | Saved; portal account created; ID has the school prefix | ☐ |
| 7.3 | Add student with missing / bad data (bad email, future birth date) | Clear field errors, nothing saved | ☐ |
| 7.4 | Add a duplicate student | Warned or refused | ☐ |
| 7.5 | Edit a student, save | Change shows in the list and profile | ☐ |
| 7.6 | Student profile and **History** | Shows changes with who and when | ☐ |
| 7.7 | Promote students to the next class | Right students moved; can be checked | ☐ |
| 7.8 | Status change (left, graduated…) | Reflected in lists and counts | ☐ |
| 7.9 | Families and Family updates | Link, edit, approve family requests | ☐ |
| 7.10 | Admission letter, ID cards, print list | Open as PDF/print with correct names and photos | ☐ |
| 7.11 | Portal logins | Letter prints; **new password** works, old one stops; **Generate missing logins** works | ☐ |
| 7.12 | Rules page | Saves, applies | ☐ |
| 7.13 | Sensitive data (SSN, health) | Masked or shown only to roles allowed | ☐ |
| 7.14 | Delete / remove a student | Asks to confirm; related data handled, no broken pages | ☐ |

---

## 8. Staff and HR

| ID | Test | Expected | Result |
|---|---|---|---|
| 8.1 | Employees list, search, add, edit, history | Works like students | ☐ |
| 8.2 | Add staff | Portal account created; ID has prefix | ☐ |
| 8.3 | Job letter, ID cards | Print correctly | ☐ |
| 8.4 | Portal logins for staff | Same as 7.11 | ☐ |
| 8.5 | Leave request, approval, leave limits | Balance updates after approval | ☐ |
| 8.6 | Rules (teaching rules: max periods etc.) | Saved; used by timetable | ☐ |
| 8.7 | Staff pay / salaries (Billing) | Calculated and shown | ☐ |

---

## 9. Admissions

| ID | Test | Expected | Result |
|---|---|---|---|
| 9.1 | Public application form `/apply/:slug` (signed out) | Submits; reference given | ☐ |
| 9.2 | Application status `/apply/status` with the reference | Shows current status | ☐ |
| 9.3 | `/apply/manage` | Applicant can update permitted details | ☐ |
| 9.4 | Staff: new application, review, accept / reject | Status changes, applicant sees it | ☐ |
| 9.5 | Convert accepted applicant to student | Student created with correct details | ☐ |
| 9.6 | Spam / blank submissions | Refused | ☐ |

---

## 10. Academics: classes, subjects, years, timetable

| ID | Test | Expected | Result |
|---|---|---|---|
| 10.1 | Academic years: add, edit, make current | Works; only one current | ☐ |
| 10.2 | Classes and sections: add, edit, view, delete | Works; students counted | ☐ |
| 10.3 | Subjects and **Assign** to classes/teachers | Saved, shows in timetable | ☐ |
| 10.4 | Courses, curriculum, topics, resources | Add, edit, link | ☐ |
| 10.5 | Timetable: periods, weekdays, rooms | Set up and saved | ☐ |
| 10.6 | Generate timetable | Created without clashes, follows teaching rules | ☐ |
| 10.7 | Editor: move a lesson into a teacher/room clash | Clash warned or refused | ☐ |
| 10.8 | Views: class, teacher, **My** timetable | Each correct for the chosen person | ☐ |
| 10.9 | Teacher leave, then **cover** for a date | Cover offered to a free teacher; shown on that day only | ☐ |
| 10.10 | Print / export timetable | Correct | ☐ |
| 10.11 | Homework: create, assign, student submits, teacher grades | Whole flow works; student and parent see result | ☐ |
| 10.12 | Late or missing submission | Marked correctly | ☐ |
| 10.13 | Lesson planner, coverage, student progress | Save and show | ☐ |
| 10.14 | Behaviour records | Add, view; parent sees allowed items | ☐ |
| 10.15 | Live class | Link / room opens | ☐ |

---

## 11. Attendance

| ID | Test | Expected | Result |
|---|---|---|---|
| 11.1 | Mark attendance for a class (present, absent, late, excused) | Saved; reopening shows the same | ☐ |
| 11.2 | Change attendance after saving | Allowed or locked per the rules; change recorded | ☐ |
| 11.3 | Lesson attendance | Works | ☐ |
| 11.4 | Absence reports | Counts match what was marked | ☐ |
| 11.5 | **Absence ladder** (3, 5, 10 unexcused) | Each step warns family, tells staff, opens an intervention as set | ☐ |
| 11.6 | Interventions list | Owner, due date, notes, session log, result, review due | ☐ |
| 11.7 | Reach panel (flagged, reached, sessions, days to start) | Numbers right | ☐ |
| 11.8 | Alerts to parents | Sent once, correct student, right language | ☐ |
| 11.9 | Face attendance | Works, or the button is hidden when not available | ☐ |
| 11.10 | Chronic absenteeism (10% or more) in reports | Correct list | ☐ |
| 11.11 | Parent and student see only their own attendance | Yes | ☐ |

---

## 12. Exams, gradebook and report cards

| ID | Test | Expected | Result |
|---|---|---|---|
| 12.1 | Exam types, grading scales, standards | Add, edit | ☐ |
| 12.2 | Create exam and schedule; datesheet | Created; clashes warned; datesheet prints | ☐ |
| 12.3 | Registrations | Students registered correctly | ☐ |
| 12.4 | Results entry | Marks saved; out-of-range marks refused | ☐ |
| 12.5 | Processing / results | Totals, grades, positions correct (check 3 students by hand) | ☐ |
| 12.6 | Award list, marksheet, exam sheet PDFs | Correct names and marks | ☐ |
| 12.7 | Class tests and question bank (chapters, create) | Work | ☐ |
| 12.8 | Gradebook | Entries roll up to the right grade | ☐ |
| 12.9 | Report cards / transcripts | Correct data, PDF opens; only the right person can open | ☐ |
| 12.10 | Exam analytics | Matches the data | ☐ |
| 12.11 | Student and parent see published results only | Yes | ☐ |

---

## 13. Billing: fees, accounts, salaries

| ID | Test | Expected | Result |
|---|---|---|---|
| 13.1 | Fee items, fee plan, discounts | Add, edit | ☐ |
| 13.2 | Fee accounts per family/student | Correct balances | ☐ |
| 13.3 | **Generate invoices** for a class | Right amount per student, none doubled when run twice | ☐ |
| 13.4 | Invoice PDF | Correct names, items, tax, total | ☐ |
| 13.5 | Collect fees (full, part payment, overpayment) | Balance updates; receipt made | ☐ |
| 13.6 | Payment plans | Instalments correct | ☐ |
| 13.7 | Online payments | Works in test mode, or says it is off | ☐ |
| 13.8 | Fees paid slip, defaulters list | Correct people | ☐ |
| 13.9 | Fee reminders | AI-prompted reminders **wait for approval**; nothing sent before | ☐ |
| 13.10 | Chart of accounts, add income, add expense, account statement | Entries balance; statement totals match | ☐ |
| 13.11 | Finance report | Totals match invoices and payments | ☐ |
| 13.12 | Currency and number formats | Right for the school's region | ☐ |
| 13.13 | Delete a payment / invoice | Confirm, audited, balances recalculated | ☐ |
| 13.14 | Parent fees page | Own children only; can see invoices and receipts | ☐ |

---

## 14. Communication

| ID | Test | Expected | Result |
|---|---|---|---|
| 14.1 | Messages: send, reply, read, attachments | Delivered to the right person only | ☐ |
| 14.2 | Announcements | Reach the chosen audience only | ☐ |
| 14.3 | Calendar: add, edit, delete event | Shows to the right audience | ☐ |
| 14.4 | Meetings (parent–teacher) | Book, change, cancel | ☐ |
| 14.5 | SMS / WhatsApp / email templates | Fill in names correctly; send in test mode | ☐ |
| 14.6 | Real-time notifications (bell) | Arrive without reload; mark read | ☐ |
| 14.7 | Auto alerts for attendance and fees | Fire once for the right people | ☐ |
| 14.8 | Language of messages | Follows the school/user setting | ☐ |

---

## 15. Campus services: library, transport, inventory, cafeteria

| ID | Test | Expected | Result |
|---|---|---|---|
| 15.1 | Library: add book, issue, return, overdue | Stock and due dates right | ☐ |
| 15.2 | Transport: fleet, routes, stops, riders, trips, boarding, notices, fees, reports | Each saves and shows | ☐ |
| 15.3 | Inventory / store: items, purchases, suppliers, report | Stock changes with purchases and use | ☐ |
| 15.4 | Cafeteria | Works as designed | ☐ |
| 15.5 | Live bus tracking | Not built; page must not claim it | ☐ |

---

## 16. Reports, analytics and AI

| ID | Test | Expected | Result |
|---|---|---|---|
| 16.1 | Each school report (enrolment, attendance, finance, results) | Loads; totals match the lists; export works | ☐ |
| 16.2 | Analytics page "At-Risk Students" | Only students the login may see | ☐ |
| 16.3 | **Risk scan** (admin) | Runs, or says it is off in the hosted demo; each scan recorded with its version | ☐ |
| 16.4 | AI Risk & Review tab: model card | States rules, inputs, versions, flag rates by group; text says scores are rule-fitted, not learned | ☐ |
| 16.5 | Human review of a risk flag | Review is recorded with who and when; survives a rescan | ☐ |
| 16.6 | Only one scan runs at a time | A second scan is refused with a clear message | ☐ |
| 16.7 | AI assistant: ask a question | Answers from live data within the asker's role | ☐ |
| 16.8 | AI assistant asked for data beyond the role | Refuses | ☐ |
| 16.9 | AI assistant can only **ask**, not act | Any action goes to approval | ☐ |
| 16.10 | SSN, birth date, health details | Masked before text goes to a provider | ☐ |
| 16.11 | "All AI" switch off | Every AI feature stops and says so | ☐ |
| 16.12 | AI drafts (lesson plan, family message, rubric) | Draft shown for editing, nothing sent automatically | ☐ |
| 16.13 | AI chat retention | Old chats removed after the set time | ☐ |

---

## 17. AI governance and approvals

| ID | Test | Expected | Result |
|---|---|---|---|
| 17.1 | AI-prompted action (e.g. fee reminder) | Waits for approval | ☐ |
| 17.2 | Approval needs **two different approvers** (admin + deputy) | One person cannot approve twice | ☐ |
| 17.3 | Named delegates | Delegate can approve; others cannot | ☐ |
| 17.4 | Change the data after approval, before running | Approval is refused and re-checked against current data | ☐ |
| 17.5 | Intent saved before the action runs | Visible in records | ☐ |
| 17.6 | Action result unconfirmed | Shown as "unknown"; a person can settle it | ☐ |
| 17.7 | Records page and file download | Lists answers, reviews, approvals, setting changes | ☐ |
| 17.8 | Audit chain check | Passes; fails if a record is tampered with (developer test) | ☐ |
| 17.9 | Model files signed | A changed model file is refused on load | ☐ |
| 17.10 | Audit logs page (`/admin/audit-logs`) | Who, what, when for logins, edits, deletes, setting changes | ☐ |

---

## 18. Settings, Admin and data tools

| ID | Test | Expected | Result |
|---|---|---|---|
| 18.1 | School profile: edit name, logo, address | Shows on letters, PDFs and the sign-in of that school | ☐ |
| 18.2 | Theme: colours, light/dark | Applies across the app; kept after reload | ☐ |
| 18.3 | Language & currency | Text and money formats change | ☐ |
| 18.4 | Plan & billing | Plan limits and gated features behave as the plan says | ☐ |
| 18.5 | Help | Opens | ☐ |
| 18.6 | Security & privacy | Settings save; privacy tools work | ☐ |
| 18.7 | Import data: upload `sample-data/us-school/us-school-pack.zip` | Preview, then import; counts match the files; errors listed by row | ☐ |
| 18.8 | Import a file with bad rows | Good rows kept or all refused as designed; clear error list | ☐ |
| 18.9 | Import the same pack twice | No duplicates | ☐ |
| 18.10 | Integrations | Connect / disconnect states shown | ☐ |
| 18.11 | All Schools (platform admin) | Lists schools; ordinary admin cannot open it | ☐ |
| 18.12 | Export data copy for one student | Complete, only that student | ☐ |

---

## 19. Phone / tablet and accessibility

| ID | Test | Expected | Result |
|---|---|---|---|
| 19.1 | At 768 px and 390 px | Menu becomes the drawer; no sideways scroll | ☐ |
| 19.2 | Drawer: open, close, open every module | Works with touch | ☐ |
| 19.3 | Forms and tables on a phone | Usable; tables scroll inside themselves | ☐ |
| 19.4 | Keyboard only through sign-in and one full task | Possible; focus visible | ☐ |
| 19.5 | Screen reader labels on buttons, star buttons, inputs | Present | ☐ |
| 19.6 | Contrast of white text on every panel colour | Readable | ☐ |
| 19.7 | Zoom to 200% | Nothing cut off | ☐ |
| 19.8 | Install as app (PWA) and offline page | Offline page appears when there is no network | ☐ |

---

## 20. Errors, performance and data safety

| ID | Test | Expected | Result |
|---|---|---|---|
| 20.1 | Server stopped, then use the app | Friendly error, no blank white page | ☐ |
| 20.2 | Open a wrong address | A proper "page not found" | ☐ |
| 20.3 | Double-click Save / Pay | Saved once only | ☐ |
| 20.4 | Large lists (83 students, many invoices) | Load in a few seconds | ☐ |
| 20.5 | Very long names, special characters, other-language text | Saved and shown correctly, no broken layout | ☐ |
| 20.6 | Browser console on every page visited | No red errors | ☐ |
| 20.7 | Reload on every page | Page returns, not blank | ☐ |
| 20.8 | Back and forward buttons | Behave | ☐ |
| 20.9 | Background jobs (briefs, alerts) | Run on schedule, in the school's time zone | ☐ |
| 20.10 | Backup and restore scripts | Restore gives the same data | ☐ |
| 20.11 | Docker build of frontend and backend | Builds | ☐ |
| 20.12 | Health check endpoint | Returns OK | ☐ |

---

## 21. End-to-end journeys (run last)

Tick only if every step passes.

| ID | Journey | Result |
|---|---|---|
| E1 | Admission → student created → class assigned → fee invoice → payment → receipt → parent sees receipt | ☐ |
| E2 | Teacher marks absent 3 days → family warned → intervention opens → counsellor logs a session → result recorded | ☐ |
| E3 | Teacher sets homework → student submits → teacher grades → parent sees grade | ☐ |
| E4 | Exam created → marks entered → results processed → report card → parent downloads own, cannot download another's | ☐ |
| E5 | Teacher on leave → cover made for the date → cover teacher sees it on their timetable | ☐ |
| E6 | AI suggests fee reminders → admin approves → deputy approves → sent → record and audit entry exist | ☐ |
| E7 | New school signs up → imports data pack → adds staff → generates timetable → school B cannot see school A | ☐ |
| E8 | Add student → portal login letter → student logs in → changes password → letter shows "Changed by user" | ☐ |

---

## 22. Defect log

| # | Test ID | Page address | Login | What happened | What was expected | Severity (High/Med/Low) | Screenshot file | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |

**Severity guide:** High = data wrong or leaked, cannot sign in, money wrong, page broken. Medium = a function fails but there is a way round. Low = looks wrong, wording, small layout.

---

## 23. Sign-off

| | Name | Date | Signature |
|---|---|---|---|
| Tester | | | |
| QA lead | | | |

**Result:** ☐ Accepted  ☐ Accepted with listed defects  ☐ Not accepted
