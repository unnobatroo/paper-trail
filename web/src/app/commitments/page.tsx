import {redirect} from "next/navigation";

// three stages became one workspace, old links still work
export default function Page() {
    redirect("/?stage=confirm");
}
