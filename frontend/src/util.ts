import { getNotificationsContext } from "svelte-notifications"

/** Helper: GET from URL as json response. */
export async function fetchJSON(url: string) {
    return fetch(url).then((r) => r.json())
}

/** Helper: Sleep for given number of ms. */
export async function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

type notificationType = "default" | "success" | "warning" | "danger"

/** Return preconfigured addNotification wrapper. */
export function getNotifier() {
    const { addNotification }: any = getNotificationsContext()
    function notify(text: string, type: notificationType = "default"): void {
        addNotification({
            text: text,
            removeAfter: 3000,
            type: type,
            position: "bottom-center",
        })
    }
    return notify
}

export function getFirstMatchingPattern(patterns, filename: string) {
    for (let pat of patterns) {
        const reg = new RegExp(`^${pat.pattern}$`)
        if (reg.test(filename)) {
            return pat
        }
    }
    return null
}

export function getSchemaFor(profile, filename: null | string) {
    if (!filename) {
        // dataset root metadata
        return profile.schemas[profile.rootSchema]
    }
    // check files
    const pat = getFirstMatchingPattern(profile.patterns, filename)
    if (pat !== null) {
        return profile.schemas[pat.useSchema]
    }
    // no match
    return profile.schemas[profile.fallbackSchema]
}
