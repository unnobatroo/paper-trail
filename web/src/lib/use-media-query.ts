"use client";

import {useMediaQuery as useBaseMediaQuery} from "@base-ui/react/unstable-use-media-query";

// false on the server and during hydration, then follows the query
export function useMediaQuery(query: string): boolean {
    return useBaseMediaQuery(query, {defaultMatches: false});
}
