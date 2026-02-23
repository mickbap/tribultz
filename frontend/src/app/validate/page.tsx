import { redirect } from "next/navigation";

export default function ValidateLegacyPage() {
  redirect("/chat");
}
