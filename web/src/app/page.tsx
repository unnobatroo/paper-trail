import { redirect } from "next/navigation";

// the stages are the app, there is no dashboard
export default function Home() {
  redirect("/commitments");
}
