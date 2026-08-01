import type { Metadata } from "next";
import { SettingsConsole } from "../components/account-console";

export const metadata: Metadata = { title: "System settings | Vidyut" };

export default function SettingsPage() {
  return <SettingsConsole />;
}
