"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "./auth";

/**
 * Client-side auth guard. Wraps protected pages and redirects to /login
 * when no token is present in sessionStorage.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const [checked, setChecked] = useState(false);

    useEffect(() => {
        if (!getToken()) {
            router.replace("/login");
        } else {
            setChecked(true);
        }
    }, [router]);

    if (!checked) return null; // avoid flash of content
    return <>{children}</>;
}
