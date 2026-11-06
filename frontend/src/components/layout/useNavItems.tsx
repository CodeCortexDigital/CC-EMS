// The menu each role sees, built in one place so the sidebar and the top menu always agree.
import React, { useState, useEffect, useRef } from 'react';
import {
  LayoutDashboard, Settings, BookOpen, GraduationCap, Users,
  Wallet, Banknote, CreditCard, Hand, Calendar, FileText,
  Eye, MessageSquare, Video, FileQuestion,
  Edit, Award, Lock, Unlock, Search, X, ChevronRight, ChevronLeft, LogOut,
  DollarSign, User, Star, Building2, ClipboardList, Mail, Megaphone, CalendarDays, Handshake, TrendingUp, Library, Bus, Boxes, UtensilsCrossed, Plug, FileSpreadsheet, ShieldCheck,
  LifeBuoy, Briefcase, ScanFace, Stethoscope, AlertOctagon, FileSignature, HeartPulse, Sparkles, ClipboardCheck, Sunrise,
} from 'lucide-react';
import cafeteriaService from '@/services/cafeteria.service';
import transportService from '@/services/transport.service';
import { useAuth } from '@/contexts/AuthContext';
import { usePermissions } from '@/hooks/usePermissions';
import { teacherQuickActions } from '@/config/teacherQuickActions';
import { usePlanStore } from '@/store/planStore';

export interface SubMenuItem {
  label: string;
  href: string;
  isLocked?: boolean;
  isLogout?: boolean;
  isDivider?: boolean;
}

export interface MenuItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  href?: string;
  isLocked?: boolean;
  isLogout?: boolean;
  subItems?: SubMenuItem[];
  /** Shown to every signed-in role (not filtered by module permissions). */
  always?: boolean;
  /** Sidebar section (nav.group_<name>); items without one sit at the top. */
  group?: string;
}

// Menu entries that belong to an optional plan module (P11).
export const PLAN_MODULE: Record<string, string> = {
  library: 'library', transport: 'transport', inventory: 'inventory', cafeteria: 'cafeteria', 'cafeteria-till': 'cafeteria',
  'bus-duty': 'transport', integrations: 'integrations', reports: 'reports', 'ai-settings': 'ai',
};

export const COMMS: MenuItem[] = [
  { id: 'messages', label: 'Messages', icon: <Mail className="w-4 h-4" />, href: '/messages', always: true, group: 'communication' },
  { id: 'announcements', label: 'Announcements', icon: <Megaphone className="w-4 h-4" />, href: '/announcements', always: true, group: 'communication' },
  { id: 'calendar', label: 'Calendar', icon: <CalendarDays className="w-4 h-4" />, href: '/calendar', always: true, group: 'communication' },
  { id: 'meetings', label: 'Meetings', icon: <Handshake className="w-4 h-4" />, href: '/meetings', always: true, group: 'communication' },
];

/** The signed-in person's menu: their role's entries, filtered by permissions and by the school's plan. */
export function useNavItems(): MenuItem[] {
  const { user, role } = useAuth();

  const isParent = role === 'parent';
  const isTeacher = role === 'teacher';
  const isStudent = role === 'student';
  const { canView, canAccess } = usePermissions();
  const [onBusDuty, setOnBusDuty] = useState(false);
  useEffect(() => {
    if (!role || ['admin', 'parent', 'student'].includes(role)) return;
    transportService.routes().then((r) => setOnBusDuty(r.length > 0)).catch(() => setOnBusDuty(false));
  }, [role]);
  // Cafeteria staff (a staff login at this school) get the till; the server decides who may use it.
  const [atTill, setAtTill] = useState(false);
  useEffect(() => {
    if (!role || ['admin', 'parent', 'student', 'teacher'].includes(role)) return;
    cafeteriaService.find('').then(() => setAtTill(true)).catch(() => setAtTill(false));
  }, [role]);

  // Admin always sees the full menu; other roles are filtered by permissions.
  const isAdmin = role === 'admin';
  usePlanStore((s) => s.sub);  // re-render when the plan loads
  const hasModule = usePlanStore((s) => s.has);

  // Map a sub-item href to the permission module it belongs to (best-effort).
  const moduleForHref = (href: string): string | null => {
    const map: Array<[RegExp, string]> = [
      [/\/education\/academic-setup/, 'academic-setup'],
      [/\/education\/timetable/, 'timetable'],
      [/\/education\/behaviour/, 'behaviour'],
      [/\/education\/skills/, 'behaviour'],
      [/\/education\/communication/, 'communication'],
      [/\/education\/exams/, 'exams'],
      [/\/education\/class-tests/, 'exams'],
      [/\/education\/analytics/, 'reports'],
      [/\/education\/attendance/, 'attendance'],
      [/\/education\/students/, 'students'],
      [/\/education\/teachers/, 'employees'],
      [/\/education\/accounts/, 'accounts'],
      [/\/education\/fees/, 'fees'],
      [/\/education\/salary/, 'salary'],
      [/\/education\/certificates/, 'certificates'],
      [/\/settings/, 'settings'],
    ];
    for (const [re, mod] of map) {
      if (re.test(href)) return mod;
    }
    return null;
  };

  // Filter a set of menu items by the current role's view permissions.
  const filterByPermissions = (items: MenuItem[]): MenuItem[] => {
    if (isAdmin) return items;
    return items
      .filter((item) => item.always || canView((item as any).module || item.id))
      .map((item) => {
        if (!item.subItems) return item;
        const subItems = item.subItems.filter((sub) => {
          if (sub.isLogout || sub.isDivider) return true;
          const mod = moduleForHref(sub.href);
          return mod ? canView(mod) : true;
        });
        return { ...item, subItems };
      });
  };

  // ============================================================
  // ADMIN MENU - Logout is INSIDE Settings subItems
  // ============================================================
  const adminMenuItems: MenuItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard className="w-4 h-4" />, href: '/dashboard' },
    ...(role === 'admin' ? [{ id: 'briefs', label: 'Daily Briefs', icon: <Sunrise className="w-4 h-4" />, href: '/education/briefs', always: true }] : []),
    ...(role === 'admin' ? [{ id: 'ai-governance', label: 'AI Approvals & Documents', icon: <ShieldCheck className="w-4 h-4" />, href: '/education/ai-governance', always: true }] : []),
    { id: 'students', label: 'Students', icon: <Users className="w-4 h-4" />, href: '/education/students', group: 'people' },
    { id: 'admissions', label: 'Admissions', icon: <ClipboardList className="w-4 h-4" />, href: '/education/admissions', group: 'people' },
    { id: 'employees', label: 'Staff', icon: <Users className="w-4 h-4" />, href: '/education/teachers', group: 'people' },
    { id: 'staff-hr', label: 'Staff & HR', icon: <Briefcase className="w-4 h-4" />, href: '/education/hr', always: true, group: 'people' },
    ...(['admin', 'front_desk'].includes(role || '') ? [{ id: 'front-desk', label: 'Front Desk', icon: <ScanFace className="w-4 h-4" />, href: '/education/front-desk', always: true, group: 'people' }] : []),
    ...(['admin', 'nurse'].includes(role || '') ? [{ id: 'health-office', label: 'Health Office', icon: <Stethoscope className="w-4 h-4" />, href: '/education/health-office', always: true, group: 'people' }] : []),
    ...(['admin', 'counsellor'].includes(role || '') ? [{ id: 'interventions', label: 'Interventions', icon: <ClipboardCheck className="w-4 h-4" />, href: '/education/interventions', always: true, group: 'people' }] : []),
    ...(['admin', 'counsellor', 'nurse', 'front_desk', 'manager', 'hr', 'staff'].includes(role || '') ? [{ id: 'safety', label: 'Safety Reports', icon: <AlertOctagon className="w-4 h-4" />, href: '/education/safety', always: true, group: 'people' }] : []),
    ...(['admin', 'manager'].includes(role || '') ? [{ id: 'forms', label: 'Forms', icon: <FileSignature className="w-4 h-4" />, href: '/education/forms', always: true, group: 'communication' }] : []),
    { id: 'academic-setup', label: 'Academic Setup', icon: <GraduationCap className="w-4 h-4" />, href: '/education/academic-setup', group: 'academics' },
    { id: 'timetable', label: 'Timetable', icon: <Calendar className="w-4 h-4" />, href: '/education/timetable', group: 'academics' },
    { id: 'attendance', label: 'Attendance', icon: <Hand className="w-4 h-4" />, href: '/education/attendance', group: 'academics' },
    { id: 'gradebook', label: 'Gradebook', icon: <BookOpen className="w-4 h-4" />, href: '/education/gradebook', group: 'academics' },
    { id: 'examination', label: 'Examination', icon: <Edit className="w-4 h-4" />, href: '/education/exams', group: 'academics' },
    { id: 'behaviour', label: 'Behaviour & Skills', icon: <Eye className="w-4 h-4" />, href: '/education/behaviour?tab=log', group: 'academics' },
    { id: 'certificates', label: 'Certificates', icon: <Award className="w-4 h-4" />, href: '/education/certificates', group: 'academics' },
    { id: 'fees', label: 'Fees', icon: <Banknote className="w-4 h-4" />, href: '/education/fees/invoices', group: 'billing' },
    { id: 'salary', label: 'Salary', icon: <DollarSign className="w-4 h-4" />, href: '/education/salary/generate', group: 'billing' },
    { id: 'accounts', label: 'Finance', icon: <Wallet className="w-4 h-4" />, href: '/education/accounts/chart-of-accounts', group: 'billing' },
    ...COMMS,
    { id: 'communication', label: 'Communication', icon: <MessageSquare className="w-4 h-4" />, href: '/education/communication', group: 'communication' },
    { id: 'library', label: 'Library', icon: <Library className="w-4 h-4" />, href: '/education/library', group: 'services' },
    { id: 'transport', label: 'Transport', icon: <Bus className="w-4 h-4" />, href: '/education/transport', group: 'services' },
    { id: 'inventory', label: 'Inventory', icon: <Boxes className="w-4 h-4" />, href: '/education/inventory', group: 'services' },
    { id: 'cafeteria', label: 'Cafeteria', icon: <UtensilsCrossed className="w-4 h-4" />, href: '/education/cafeteria', group: 'services' },
    { id: 'reports', label: 'Reports', icon: <TrendingUp className="w-4 h-4" />, href: isAdmin ? '/education/analytics/insights' : '/education/analytics', group: 'reports' },
    { id: 'security', label: 'Security & privacy', icon: <Lock className="w-4 h-4" />, href: '/settings/security', group: 'admin' },
    { id: 'help', label: 'Help & support', icon: <LifeBuoy className="w-4 h-4" />, href: '/help', always: true, group: 'settings' },
    { id: 'import-data', label: 'Import data', icon: <FileSpreadsheet className="w-4 h-4" />, href: '/education/import', group: 'admin' },
    { id: 'ai-settings', label: 'AI Assistant', icon: <Sparkles className="w-4 h-4" />, href: '/settings/ai', group: 'admin' },
    { id: 'integrations', label: 'Integrations', icon: <Plug className="w-4 h-4" />, href: '/settings/integrations', group: 'admin' },
    { id: 'settings', label: 'Settings', icon: <Settings className="w-4 h-4" />, href: '/settings', group: 'settings' },
    // Platform owner only: every school on this installation.
    ...(user?.is_superuser
      ? [{ id: 'platform', label: 'All Schools', icon: <Building2 className="w-4 h-4" />, href: '/platform/schools', group: 'admin' }]
      : []),
  ];

  // Teacher Menu - derived from the SAME permission-filtered quick
  // actions as the dashboard, so the sidebar and portal stay in sync.
  // Only "Dashboard" is kept as a fixed item; everything else comes
  // from the RBAC-driven quick-action list (filtered by `canView`).
  const teacherMenuItems: MenuItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
      href: '/teacher',
    },
    { id: 'my-classes', label: 'My Classes', icon: <GraduationCap className="w-4 h-4" />, href: '/teacher/classes', always: true, group: 'teaching' },
    { id: 'class-reports', label: 'Class Reports', icon: <ClipboardList className="w-4 h-4" />, href: '/teacher/reports', always: true, group: 'teaching' },
    { id: 'staff-hr', label: 'Cover & My HR', icon: <Briefcase className="w-4 h-4" />, href: '/education/hr/cover', always: true, group: 'teaching' },
    { id: 'safety', label: 'Safety Reports', icon: <AlertOctagon className="w-4 h-4" />, href: '/education/safety', always: true, group: 'teaching' },
    { id: 'interventions', label: 'My Interventions', icon: <ClipboardCheck className="w-4 h-4" />, href: '/education/interventions', always: true, group: 'teaching' },
    { id: 'library', label: 'Library', icon: <Library className="w-4 h-4" />, href: '/library', always: true, group: 'services' },
    ...teacherQuickActions
      .filter((q) => canView(q.module))
      .map((q) => ({
        id: q.id,
        module: q.module,
        label: q.label,
        icon: <q.icon className="w-4 h-4" />,
        href: q.href,
        group: 'teaching',
      })),
    ...COMMS,
    { id: 'privacy', label: 'Privacy & consent', icon: <ShieldCheck className="w-4 h-4" />, href: '/privacy', always: true, group: 'account' },
    { id: 'help', label: 'Help & support', icon: <LifeBuoy className="w-4 h-4" />, href: '/help', always: true, group: 'account' },
    {
      id: 'settings',
      label: 'Account Settings',
      icon: <Settings className="w-4 h-4" />,
      group: 'account',
      subItems: [
        { label: 'Account Settings', href: '/settings/account' },
        { label: '──────────', href: '#', isDivider: true },
        { label: 'Log out', href: '#logout', isLogout: true },
      ],
    },
  ];


  // Student Menu - with Logout inside Settings
  const studentMenuItems: MenuItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
      href: '/student'
    },
    {
      id: 'profile',
      label: 'My Profile',
      icon: <User className="w-4 h-4" />,
      href: '/student/profile',
      group: 'learning'
    },
    {
      id: 'attendance',
      label: 'Attendance',
      icon: <Calendar className="w-4 h-4" />,
      href: '/student/attendance',
      group: 'learning'
    },
    {
      id: 'results',
      label: 'Results',
      icon: <Award className="w-4 h-4" />,
      href: '/student/results',
      group: 'learning'
    },
    {
      id: 'assignments',
      label: 'Assignments',
      icon: <BookOpen className="w-4 h-4" />,
      href: '/student/assignments',
      group: 'learning',
      always: true
    },
    {
      id: 'progress',
      label: 'Progress',
      icon: <TrendingUp className="w-4 h-4" />,
      href: '/student/progress',
      group: 'learning',
      always: true
    },
    {
      id: 'timetable',
      label: 'My Timetable',
      icon: <Calendar className="w-4 h-4" />,
      href: '/student/timetable',
      group: 'learning'
    },
    {
      id: 'behaviour',
      label: 'Behaviour & Skills',
      icon: <Star className="w-4 h-4" />,
      href: '/student/behaviour',
      group: 'learning'
    },
    {
      id: 'fees',
      label: 'Fees',
      icon: <Wallet className="w-4 h-4" />,
      href: '/student/fees',
      group: 'billing'
    },
    {
      id: 'documents',
      label: 'Documents',
      icon: <FileText className="w-4 h-4" />,
      href: '/student/documents',
      group: 'learning',
      always: true
    },
    {
      id: 'certificates',
      label: 'Certificates',
      icon: <Award className="w-4 h-4" />,
      href: '/student/certificates',
      group: 'learning'
    },
    {
      id: 'library',
      label: 'Library',
      icon: <Library className="w-4 h-4" />,
      href: '/student/library',
      group: 'services',
      always: true
    },
    {
      id: 'transport',
      label: 'Transport',
      icon: <Bus className="w-4 h-4" />,
      href: '/student/transport',
      group: 'services',
      always: true
    },
    {
      id: 'cafeteria',
      label: 'Cafeteria',
      icon: <UtensilsCrossed className="w-4 h-4" />,
      href: '/student/cafeteria',
      group: 'services',
      always: true
    },
    ...COMMS,
    { id: 'privacy', label: 'Privacy & consent', icon: <ShieldCheck className="w-4 h-4" />, href: '/privacy', always: true, group: 'account' },
    { id: 'help', label: 'Help & support', icon: <LifeBuoy className="w-4 h-4" />, href: '/help', always: true, group: 'account' },
    {
      id: 'notifications',
      label: 'Notifications',
      icon: <MessageSquare className="w-4 h-4" />,
      href: '/student/notifications',
      group: 'communication'
    },
    {
      id: 'settings',
      label: 'Account Settings',
      icon: <Settings className="w-4 h-4" />,
      group: 'account',
      subItems: [
        { label: 'Account Settings', href: '/settings/account' },
        { label: '──────────', href: '#', isDivider: true },
        { label: 'Log out', href: '#logout', isLogout: true }
      ]
    }
  ];

  // Parent Menu - one account for the whole family; pages switch between children.
  const P = (id: string, label: string, icon: React.ReactNode, href: string, group?: string): MenuItem => ({ id, label, icon, href, always: true, group });
  const parentMenuItems: MenuItem[] = [
    P('dashboard', 'Dashboard', <LayoutDashboard className="w-4 h-4" />, '/parent'),
    P('my-family', 'My Family', <Users className="w-4 h-4" />, '/parent/children', 'family'),
    P('attendance', 'Attendance', <Calendar className="w-4 h-4" />, '/parent/attendance', 'family'),
    P('assignments', 'Assignments', <BookOpen className="w-4 h-4" />, '/parent/assignments', 'family'),
    P('progress', 'Progress', <TrendingUp className="w-4 h-4" />, '/parent/progress', 'family'),
    P('behaviour', 'Behaviour & Skills', <Star className="w-4 h-4" />, '/parent/behaviour', 'family'),
    P('fees', 'Fees & Billing', <Wallet className="w-4 h-4" />, '/parent/fees', 'billing'),
    P('documents', 'Documents', <FileText className="w-4 h-4" />, '/parent/documents', 'family'),
    P('forms', 'Forms to Sign', <FileSignature className="w-4 h-4" />, '/parent/forms', 'family'),
    P('health', 'Health', <HeartPulse className="w-4 h-4" />, '/parent/health', 'family'),
    P('applications', 'Applications', <ClipboardList className="w-4 h-4" />, '/parent/applications', 'family'),
    P('library', 'Library', <Library className="w-4 h-4" />, '/parent/library', 'services'),
    P('transport', 'Transport', <Bus className="w-4 h-4" />, '/parent/transport', 'services'),
    P('cafeteria', 'Cafeteria', <UtensilsCrossed className="w-4 h-4" />, '/parent/cafeteria', 'services'),
    ...COMMS,
    { id: 'privacy', label: 'Privacy & consent', icon: <ShieldCheck className="w-4 h-4" />, href: '/privacy', always: true, group: 'account' },
    { id: 'help', label: 'Help & support', icon: <LifeBuoy className="w-4 h-4" />, href: '/help', always: true, group: 'account' },
    P('notifications', 'Notifications', <MessageSquare className="w-4 h-4" />, '/parent/notifications', 'communication'),
    {
      id: 'settings',
      label: 'Account Settings',
      icon: <Settings className="w-4 h-4" />,
      group: 'account',
      always: true,
      subItems: [
        { label: 'Account Settings', href: '/settings/account' },
        { label: '──────────', href: '#', isDivider: true },
        { label: 'Log out', href: '#logout', isLogout: true }
      ]
    }
  ];

  let menuItems = isTeacher ? teacherMenuItems : isStudent ? studentMenuItems : isParent ? parentMenuItems : adminMenuItems;
  // Drivers and attendants (often teachers or staff with a login) get "Bus duty" once they are on a route.
  if (onBusDuty && !isAdmin && !isParent && !isStudent) {
    const duty: MenuItem = { id: 'bus-duty', label: 'Bus Duty', icon: <Bus className="w-4 h-4" />, href: '/transport/duty', always: true };
    menuItems = [menuItems[0], duty, ...menuItems.slice(1)];
  }
  if (atTill && !isAdmin && !isParent && !isStudent) {
    const till: MenuItem = { id: 'cafeteria-till', label: 'Cafeteria Till', icon: <UtensilsCrossed className="w-4 h-4" />, href: '/cafeteria/till', always: true };
    menuItems = [menuItems[0], till, ...menuItems.slice(1)];
  }
  menuItems = filterByPermissions(menuItems);
  // Optional areas outside the school's plan are hidden (the server refuses them anyway).
  menuItems = menuItems.filter((item) => {
    const module = PLAN_MODULE[item.id];
    return !module || hasModule(module);
  });

  return menuItems;
}
