import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { Busy } from "@/components/ui";

const Today = lazy(() => import("@/pages/Today"));
const Topics = lazy(() => import("@/pages/Topics"));
const Accounts = lazy(() => import("@/pages/Accounts"));
const Articles = lazy(() => import("@/pages/Articles"));
const Tasks = lazy(() => import("@/pages/Tasks"));
const Publish = lazy(() => import("@/pages/Publish"));
const Knowledge = lazy(() => import("@/pages/Knowledge"));
const Settings = lazy(() => import("@/pages/Settings"));

export default function App() {
  return <AppShell><Suspense fallback={<Busy />}><Routes>
    <Route path="/" element={<Today />} />
    <Route path="/topics/:source" element={<Topics />} />
    <Route path="/accounts" element={<Accounts />} />
    <Route path="/articles/:id?" element={<Articles />} />
    <Route path="/tasks/:id?" element={<Tasks />} />
    <Route path="/publish" element={<Publish />} />
    <Route path="/knowledge" element={<Knowledge />} />
    <Route path="/settings" element={<Settings />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense></AppShell>;
}
