import type { Metadata } from "next";
import { ProfileConsole } from "../components/account-console";

export const metadata: Metadata = { title: "Operator profile | Vidyut" };

export default function ProfilePage() {
  return <ProfileConsole />;
}
