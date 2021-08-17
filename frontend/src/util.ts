/** Helper: GET from URL as json response */
export function fetchJSON(url) {
    return fetch(url).then((r) => r.json())
}

export function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
}
