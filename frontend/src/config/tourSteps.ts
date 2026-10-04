// The first-sign-in tour: a few short steps per kind of person, each pointing at a page that person can open.
// The wording follows docs/USER_MANUAL.md. Bump a tour's `version` to show it once more to everyone.

export interface TourStep { title: string; body: string; href?: string; linkLabel?: string }
export interface Tour { key: string; version: number; steps: TourStep[] }

const INSTALL: TourStep = {
  title: 'Install the app and get alerts',
  body: 'In Account Settings you can install the portal on your phone or computer, and choose which notifications are sent to your device.',
  href: '/settings/account', linkLabel: 'Open Account Settings',
};
const HELP: TourStep = {
  title: 'Help is always here',
  body: 'Help & support has guides for every area. You can replay this tour from there at any time.',
  href: '/help', linkLabel: 'Open Help & support',
};

const TOURS: Record<string, Tour> = {
  admin: {
    key: 'admin', version: 2, steps: [
      { title: 'Welcome to your school', body: 'This is a short tour of where things are. The menu on the left is grouped by job: People, Academics, Billing, Communication and more. Click a heading to open it.' },
      { title: 'Students and families', body: 'Find students, add new ones, see households, print ID cards, and give students and parents their passwords under Portal Logins.', href: '/education/students', linkLabel: 'Open Students' },
      { title: 'Admissions', body: 'Online applications, the waiting list with automatic seat offers, school tours and interviews, and each family\'s document checklist.', href: '/education/admissions', linkLabel: 'Open Admissions' },
      { title: 'Staff & HR', body: 'Cover requests, who is out, recruitment, contracts and licences, performance and pay set-up. Approved leave finds substitute cover automatically.', href: '/education/hr', linkLabel: 'Open Staff & HR' },
      { title: 'Timetable', body: 'Build the week for every class using only qualified teachers. Teaching Rules says who can teach which subject.', href: '/education/timetable', linkLabel: 'Open Timetable' },
      { title: 'Fees', body: 'Generate invoices for a class, take payments, and see who has not paid. Families can pay by card online.', href: '/education/fees/invoices', linkLabel: 'Open Fees' },
      { title: 'Interventions', body: 'A to-do list for helping individual students. Interventions open on their own when absences add up (you set the steps under Attendance) or the early-warning model flags a student. Give each one an owner and a due date.', href: '/education/interventions', linkLabel: 'Open Interventions' },
      { title: 'Safety, health and front desk', body: 'Report and follow up incidents, record nurse visits and medication, and control who may collect each child.', href: '/education/safety', linkLabel: 'Open Safety reports' },
      { title: 'Forms and permission slips', body: 'Send a form to a class or the whole school, collect signatures online, and remind the families who have not signed.', href: '/education/forms', linkLabel: 'Open Forms' },
      { title: 'Import and export', body: 'Load a whole school from spreadsheets, download everything as a backup, or restore it. Nothing is saved until you check the preview and press Import.', href: '/education/import', linkLabel: 'Open Import data' },
      INSTALL, HELP,
    ],
  },
  teacher: {
    key: 'teacher', version: 1, steps: [
      { title: 'Welcome', body: 'Your menu has your classes, reports, cover requests and messages. Here is a quick look.' },
      { title: 'Your classes', body: 'See your classes and students, mark attendance and enter marks.', href: '/teacher/classes', linkLabel: 'Open My Classes' },
      { title: 'Cover and your own HR', body: 'If a colleague is away you may be asked to cover a lesson: press "I can cover" if you are free. Request your own leave here too.', href: '/education/hr/cover', linkLabel: 'Open Cover & My HR' },
      { title: 'Reporting an incident', body: 'If a student is hurt, or there is bullying or damage, file a safety report. You can see the reports you filed.', href: '/education/safety', linkLabel: 'Open Safety reports' },
      { title: 'Messages', body: 'Talk to families and colleagues. Announcements from the school appear here too.', href: '/messages', linkLabel: 'Open Messages' },
      INSTALL, HELP,
    ],
  },
  parent: {
    key: 'parent', version: 1, steps: [
      { title: 'Welcome', body: 'One account covers all of your children. Use the menu to switch between them on each page.' },
      { title: 'Your family', body: 'Your children\'s details, attendance, assignments, progress and behaviour.', href: '/parent/children', linkLabel: 'Open My Family' },
      { title: 'Forms to sign', body: 'Permission slips and consent forms from the school appear here, one for each child. Read, sign with your name, and you are done.', href: '/parent/forms', linkLabel: 'Open Forms to sign' },
      { title: 'Fees and billing', body: 'See what is due and pay by card.', href: '/parent/fees', linkLabel: 'Open Fees & Billing' },
      { title: 'Health at school', body: 'Visits to the school nurse and the medicine the school may give your child.', href: '/parent/health', linkLabel: 'Open Health' },
      INSTALL, HELP,
    ],
  },
  student: {
    key: 'student', version: 1, steps: [
      { title: 'Welcome', body: 'Everything you need for school is in the menu on the left.' },
      { title: 'Your timetable', body: 'See where you need to be and when.', href: '/student/timetable', linkLabel: 'Open My Timetable' },
      { title: 'Assignments and results', body: 'Find your homework and see how you are doing.', href: '/student/assignments', linkLabel: 'Open Assignments' },
      INSTALL, HELP,
    ],
  },
  front_desk: {
    key: 'front_desk', version: 1, steps: [
      { title: 'Welcome to the front desk', body: 'You handle pickup and visitors. Both are one click away.' },
      { title: 'Pickup', body: 'Find the student, check who may collect them, check photo ID, and press Release. Anyone marked DO NOT RELEASE is stopped: ask an administrator.', href: '/education/front-desk', linkLabel: 'Open Pickup' },
      { title: 'Visitors', body: 'Sign visitors in and out. The "On site now" list is what you need in an emergency, and you can print it.', href: '/education/front-desk/visitors', linkLabel: 'Open Visitors' },
      INSTALL, HELP,
    ],
  },
  nurse: {
    key: 'nurse', version: 1, steps: [
      { title: 'Welcome to the health office', body: 'Record each visit and each dose of medicine. Parents are told about visits automatically.' },
      { title: 'Visits and medication', body: 'Find the student, then add a visit, or give a dose from the medication tab. The system warns you if a dose is too soon after the last one.', href: '/education/health-office', linkLabel: 'Open Health office' },
      INSTALL, HELP,
    ],
  },
  counsellor: {
    key: 'counsellor', version: 2, steps: [
      { title: 'Welcome', body: 'You see every safety report and run the follow-up.' },
      { title: 'Interventions', body: 'Students who need support appear here: after repeated absences, or when the early-warning model flags them. Assign an owner, keep notes, and mark each done when something has been done.', href: '/education/interventions', linkLabel: 'Open Interventions' },
      { title: 'Safety reports', body: 'Open a report, add follow-up tasks with an owner and a due date, and close it with a note when it is resolved. Overdue tasks are flagged at the top.', href: '/education/safety', linkLabel: 'Open Safety reports' },
      INSTALL, HELP,
    ],
  },
  staff: {
    key: 'staff', version: 1, steps: [
      { title: 'Welcome', body: 'Here is a quick look at what you can do.' },
      { title: 'Cover and your own HR', body: 'Lessons that need covering, who is out, and your own leave and records.', href: '/education/hr/cover', linkLabel: 'Open Cover & My HR' },
      { title: 'Reporting an incident', body: 'File a safety report if a student is hurt, or there is bullying or damage.', href: '/education/safety', linkLabel: 'Open Safety reports' },
      INSTALL, HELP,
    ],
  },
};
TOURS.manager = { ...TOURS.staff, key: 'manager' };
TOURS.hr = { ...TOURS.staff, key: 'hr' };

/** The tour for a signed-in role, or null when that role has none. */
export function tourFor(role: string | null | undefined): Tour | null {
  return (role && TOURS[role]) || null;
}

export const ALL_TOURS = TOURS;
