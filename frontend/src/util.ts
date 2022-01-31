import { getNotificationsContext } from "svelte-notifications"

export type JSONVal =
    | string
    | number
    | boolean
    | null
    | JSONVal[]
    | { [key: string]: JSONVal }

/** Helper: GET from URL as json response. */
export function fetchJSON(url: string, args?: RequestInit): Promise<JSONVal> {
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
export async function sleep(ms: number): Promise<number> {
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
export function getNotifier(): (msg: string, nType?: notificationType) => void {
    const { addNotification }: any = getNotificationsContext()
    function notify(msg: string, type: notificationType = "default"): void {
        console.log(typeToLoglevel[type] + ": " + msg)
        addNotification({
            text: msg,
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
    schemas: { [name: string]: JSONVal }
    patterns: Pattern[]
    rootSchema: string
    fallbackSchema: string
}

export type FileInfos = { [name: string]: { checksum: string | null; metadata: JSONVal } }

export type Dataset = {
    id: string
    creator: string
    created: string
    expires: string
    checksumAlg: string
    profile: Profile
    rootMeta: JSONVal
    files: FileInfos
}

export function getFirstMatchingPattern(
    patterns: Pattern[],
    filename: string
): Pattern | null {
    for (const pat of patterns) {
        const reg = new RegExp(`^${pat.pattern}$`, "i") // case-insensitive full match
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

/** Deep copy a JSON object.  */
export function deepCopyJSON(json: JSONVal): JSONVal {
    return JSON.parse(JSON.stringify(json))
}

/** Recursively traverse the $ref entries in the given schema, apply function to value. */
function traverseRefs(o: JSONVal, func: (_: string) => string): void {
    // match on JSON type for recursion
    if (Array.isArray(o)) {
        for (const child of o) {
            traverseRefs(child, func)
        }
    } else if (o instanceof Object) {
        // not array -> must be object
        for (const k of Object.keys(o)) {
            if (k == "$ref") {
                //we know the value is a string (assuming a valid schema)
                o[k] = func(o[k] as string)
            } else {
                traverseRefs(o[k], func)
            }
        }
    }
    // otherwise: primitive (null, boolean, string, number) -> nothing to do
}

/**
 * Rewire refs in that specific schema by prepending "#/$defs/".
 * If preserveInternal is set, does not touch local refs #/...
 *
 * Arguments:
 * refstr: current value of a $ref field in some schema
 * preserveInternal: do not rewrite local (#/[...]) refs, UNLESS they are #/$defs/[...].
 *   Set this to true when processing the "main" schema.
 * suf: suffix to add in case of internal references of embedded schemas.
 *   set this to /schemaName when processing schemaName as embedded entity.
 */
function fixRefs(refstr: string, preserveInternal: boolean, suf = ""): string {
    const [schemaName, fragm] = refstr.split("#")
    const fragmentPath = fragm ? fragm : "" // for case that no # symbol in string

    const isInternal = schemaName == ""
    const isNotInternalDefs = fragmentPath.slice(0, 7) != "/$defs/"
    if (preserveInternal && isInternal && isNotInternalDefs) {
        // if set, we're scanning the "root" schema, so local refs should stay untouched
        // EXCEPT for stuff under $defs, which moves one level deeper
        return refstr
    }
    return (
        "#/$defs" +
        (isInternal ? suf : "") +
        (!isInternal ? "/" : "") +
        schemaName +
        fragmentPath
    )
}

/**
 * Make a schema in the profile self-contained by embedding the other schemas in it.
 *
 * Assumption: there are no "real" external references anymore, i.e.
 * all refs are schemaName#/json/pointer
 * (referring to a name in profile.schemas that possibly was a file in the profiles dir)
 * external refs (absolute URLs/files) are embedded in profile.schemas as names for lookup
 * on the backend side, in the same way as files.
 * Also, profile.schemas must not contain a key "$defs".
 */
export function selfContainedSchema(profile: Profile, schemaName: string): JSONVal {
    //copy requested main schema
    const ret = deepCopyJSON(profile.schemas[schemaName])
    if (typeof ret == "boolean") {
        return ret //boolean schema -> nothing to do
    }
    //fix $refs (not touching document-local #/... refs)
    traverseRefs(ret, (s) => fixRefs(s, true))

    //copy schemas for embedding and fix document-local $refs to their new location
    const schemas = deepCopyJSON(profile.schemas)
    for (const [name, schema] of Object.entries(schemas)) {
        traverseRefs(schema, (s) => fixRefs(s, false, "/" + name))
    }
    //relocate own embedded defs one level deeper
    if (ret["$defs"]) {
        schemas["$defs"] = ret["$defs"]
    }
    ret["$defs"] = schemas
    return ret
}
