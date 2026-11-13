import { Outlet } from 'react-router-dom';
import DemoBanner from '@/components/common/DemoBanner';

export default function StudentPortalLayout() {
  return (
    <>
      <DemoBanner />
      <Outlet />
    </>
  );
}
