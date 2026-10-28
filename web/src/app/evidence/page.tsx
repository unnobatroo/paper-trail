import { redirect } from "next/navigation";

// the three stages became one workspace, keep old links working
export default function Page() {
  redirect("/?stage=review");
}
