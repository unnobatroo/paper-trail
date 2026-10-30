import {useMediaQuery} from "@/lib/use-media-query"

const MOBILE_BREAKPOINT = 768
const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

export function useIsMobile() {
    return useMediaQuery(QUERY)
}
