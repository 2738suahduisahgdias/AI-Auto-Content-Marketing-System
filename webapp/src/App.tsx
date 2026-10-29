import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { Busy } from "@/components/ui";

const Today = lazy(() => import("@/pages/Today"));
const Topics = lazy(() => import("@/pages/Topics"));
const Accounts = lazy(() => import("@/pages/AccountAnalytics"));
const Competitors = lazy(() => import("@/pages/Competitors"));
const Retrospective = lazy(() => import("@/pages/Retrospective"));
const Articles = lazy(() => import("@/pages/Articles"));
const Tasks = lazy(() => import("@/pages/Tasks"));
const Review = lazy(() => import("@/pages/Review"));
const Publish = lazy(() => import("@/pages/Publish"));
const Knowledge = lazy(() => import("@/pages/Knowledge"));
const CollectionKnowledge = lazy(() => import("@/pages/CollectionKnowledge"));
const Settings = lazy(() => import("@/pages/Settings"));
const Setup = lazy(() => import("@/pages/Setup"));

export default function App() {
  return <AppShell><Suspense fallback={<Busy />}><Routes>
    <Route path="/" element={<Today />} />
    <Route path="/topics/:source" element={<Topics />} />
    <Route path="/accounts/:view?" element={<Accounts />} />
    <Route path="/competitors" element={<Competitors />} />
    <Route path="/retrospective" element={<Retrospective />} />
    <Route path="/articles/:id?" element={<Articles />} />
    <Route path="/tasks/:id?" element={<Tasks />} />
    <Route path="/review" element={<Review />} />
    <Route path="/publish" element={<Publish />} />
    <Route path="/knowledge" element={<Knowledge />} />
    <Route path="/knowledge/collection" element={<CollectionKnowledge />} />
    <Route path="/settings" element={<Settings />} />
    <Route path="/setup" element={<Setup />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense></AppShell>;
}
