<script lang="ts">
    import { onMount } from "svelte"
    import { fetchJSON } from "./util"
    import { navigate, useLocation } from "svelte-navigator"
    import "../node_modules/picnic/picnic.min.css"

    // The button should react to changes of the URL...
    const loc = useLocation()

    // authentication redirects back to same location as before, except after signout
    let auth_link: string = ""
    $: auth_link =
        "/oauth/orcid?state=" + ($loc.pathname != "/signout" ? $loc.pathname : "/")

    // Grab authentication state when loading component
    let auth_status = null
    export let userSession = null

    let currTime = Date.now()
    let remainingTime: number
    $: remainingTime = userSession
        ? new Date(userSession.expires).getTime() - currTime
        : remainingTime

    function formatTime(date: Date): string {
        return date.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        })
    }

    /** Update time, sign user out if expired. */
    function checkTime() {
        currTime = Date.now()
        if (remainingTime <= 0 && userSession) {
            signOut()
        }
    }

    onMount(async () => {
        auth_status = await fetchJSON("/oauth/status")
        userSession = auth_status.session
        setInterval(checkTime, 500)
    })

    /** Greet the identified user. */
    function greeting({ session }) {
        if (session != null) {
            return "Hello, " + session.user_name + "!"
        } else {
            return ""
        }
    }

    /** Sign out user on server and remove local auth information. */
    function signOut() {
        fetch("/oauth/signout").then((r) => {
            //note: can't use fetchJSON, is a redirect
            if (r.status != 200) {
                console.log("WARNING: signout at server failed. We can still proceed.")
            }
            userSession = auth_status.session = null // forget the session locally, too
            navigate("/signout", { replace: true }) //redirect to signout page
        })
    }
</script>

{#if auth_status}
    <span id="auth-button" v-if="global.auth.orcid_enabled">
        {greeting(auth_status)}
        {#if auth_status.session == null}
            <span id="signin-button">
                <link
                    rel="stylesheet"
                    href="https://cdn.jsdelivr.net/gh/jpswalsh/academicons/css/academicons.min.css" />
                <a class="button" href={auth_link}>
                    <i class="ai ai-orcid" /> Sign in with ORCID
                </a>
            </span>
        {:else}
            Your session ends in: <span class:urgent={remainingTime < 600}>
                {formatTime(new Date(remainingTime))}</span>
            <span id="signout-button">
                <a class="button" href={"#"} on:click={signOut}>Sign out</a>
            </span>
        {/if}
    </span>
{/if}

<style>
    .urgent {
        font-weight: bold;
        color: red;
    }
</style>
