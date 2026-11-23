import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import type { Role } from "./lib/api";
import { HOME, useSession } from "./lib/session";
import { Audit } from "./pages/app/Audit";
import { Classes } from "./pages/app/Classes";
import { Coverage } from "./pages/app/Coverage";
import { System } from "./pages/app/System";
import { Cluster, ClusterSchool } from "./pages/app/Cluster";
import { Dashboard } from "./pages/app/Dashboard";
import { Duplicates } from "./pages/app/Duplicates";
import { Export } from "./pages/app/Export";
import { MyRecord } from "./pages/app/MyRecord";
import { Rules } from "./pages/app/Rules";
import { Upload } from "./pages/app/Upload";
import { Enter } from "./pages/Enter";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";
import { Styleguide } from "./pages/Styleguide";

/** UI convenience only: the backend enforces the same rules on every request. */
function Only({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { identity } = useSession();
  if (identity && !roles.includes(identity.role)) return <Navigate to={HOME[identity.role]} replace />;
  return <>{children}</>;
}

function AppHome() {
  const { identity } = useSession();
  return <Navigate to={identity ? HOME[identity.role] : "/enter"} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/enter" element={<Enter />} />
      <Route path="/styleguide" element={<Styleguide />} />
      <Route path="/app" element={<AppShell />}>
        <Route index element={<AppHome />} />
        <Route path="dashboard" element={<Only roles={["principal", "teacher", "mis_coordinator", "admin"]}><Dashboard /></Only>} />
        <Route path="upload" element={<Only roles={["principal"]}><Upload /></Only>} />
        <Route path="duplicates" element={<Only roles={["principal", "mis_coordinator", "admin"]}><Duplicates /></Only>} />
        <Route path="export" element={<Only roles={["principal", "mis_coordinator"]}><Export /></Only>} />
        <Route path="rules" element={<Rules />} />
        <Route path="cluster" element={<Only roles={["mis_coordinator", "admin"]}><Cluster /></Only>} />
        <Route path="cluster/:code" element={<Only roles={["mis_coordinator", "admin"]}><ClusterSchool /></Only>} />
        <Route path="classes" element={<Only roles={["teacher"]}><Classes /></Only>} />
        <Route path="my-record" element={<Only roles={["student_parent"]}><MyRecord /></Only>} />
        <Route path="audit" element={<Only roles={["admin"]}><Audit /></Only>} />
        <Route path="coverage" element={<Only roles={["principal", "mis_coordinator", "admin"]}><Coverage /></Only>} />
        <Route path="system" element={<Only roles={["admin"]}><System /></Only>} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
