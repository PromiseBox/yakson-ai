import { redirect } from "next/navigation";

export default function LegacyCheckPage() {
  redirect("/patients");
}
