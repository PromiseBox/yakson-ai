import { redirect } from "next/navigation";

export default async function LegacyReportPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(id === "demo-latest" ? "/reports/patient_hong" : `/reports/${id}`);
}
