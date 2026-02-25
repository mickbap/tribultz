import { redirect } from "next/navigation";

export default function ValidateLegacyPage() {
  redirect("/validate-xml");
}
