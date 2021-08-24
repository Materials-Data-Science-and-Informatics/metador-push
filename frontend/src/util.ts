import { getNotificationsContext } from "svelte-notifications"

export type JSONVal =
    | string
    | number
    | boolean
    | null
    | JSONVal[]
    | { [key: string]: JSONVal }

/** Helper: GET from URL as json response. */
export function fetchJSON(url: string, args?: any): Promise<any> {
    return new Promise((resolve, reject) => {
        fetch(url, args)
            .then((response) => {
                response.json().then((val) => {
                    if (response.ok) {
                        resolve(val)
                    } else {
                        reject(val)
                    }
                })
            })
            .catch((err) => {
                reject(err)
            })
    })
}

/** Helper: Sleep for given number of ms. */
export async function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

// the notification styles of svelte-notifications:
type notificationType = "default" | "success" | "warning" | "danger"

// typical log-level names for showing the notification text in log:
const typeToLoglevel = {
    default: "INFO",
    success: "INFO",
    warning: "WARNING",
    danger: "ERROR",
}

/** Return preconfigured addNotification wrapper. */
export function getNotifier() {
    const { addNotification }: any = getNotificationsContext()
    function notify(text: string, type: notificationType = "default"): void {
        console.log(typeToLoglevel[type] + ": " + text)
        addNotification({
            text: text,
            removeAfter: 3000,
            type: type,
            position: "bottom-center",
        })
    }
    return notify
}

export type Pattern = {
    pattern: string
    useSchema: string
}

export type Profile = {
    title: string
    description: string
    schemas: { [name: string]: any }
    patterns: Pattern[]
    rootSchema: string
    fallbackSchema: string
}

export type FileInfos = { [name: string]: { checksum: string | null; metadata: any } }

export type Dataset = {
    id: string
    creator: string
    created: string
    expires: string
    checksumTool: string
    profile: Profile
    rootMeta: any
    files: FileInfos
}

export function getFirstMatchingPattern(
    patterns: Pattern[],
    filename: string
): Pattern | null {
    for (let pat of patterns) {
        const reg = new RegExp(`^${pat.pattern}$`)
        if (reg.test(filename)) {
            return pat
        }
    }
    return null
}

export function getSchemaNameFor(profile: Profile, filename: string | null): string {
    if (!filename) {
        // dataset root metadata
        return profile.rootSchema
    }
    // check files
    const pat = getFirstMatchingPattern(profile.patterns, filename)
    if (pat !== null) {
        return pat.useSchema
    }
    // no match
    return profile.fallbackSchema
}

export function selfContainedSchema(profile: Profile, schemaName: string) {
    return profile.schemas[schemaName]
    // TODO: copy profile.schemas into schema.definitions
    // rewire all $refs correctly
}
