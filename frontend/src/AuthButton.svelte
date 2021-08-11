<script lang="ts">
	import {onMount} from "svelte";
	import {fetchJSON} from "./util.ts";
	import {navigate, useLocation} from "svelte-navigator";
	import "../node_modules/picnic/picnic.min.css"

	// The button should react to changes of the URL...
	const loc = useLocation();
	let curpath = $loc.pathname
	// authentication redirects back to same location as before, except after signout
	let auth_link = "/oauth/orcid?state=" + (curpath != "/signout" ? curpath : "/");

	// Grab authentication state when loading component
	let auth_status = null;
	export let userSession = null;

	onMount(async () => {
		auth_status = await fetchJSON('/oauth/status');
		userSession = auth_status.session;
	});

	// Greet the identified user
	function greeting({session}) {
		if (session != null) {
			return "Hello, " + session.user_name + "!";
		} else {
			return "";
		}
	}

	function signOut() {
		fetch('/oauth/signout').then(r => {
			if (r.status != 200) {
				console.log("WARNING: signout at server failed. We can still proceed.")
			}
			userSession = auth_status.session = null; // forget the session locally, too
			navigate("/signout", { replace: true }); //redirect to signout page
		})
	}

	//TODO: if session expires soon, show countdown and warn?

</script>

{#if auth_status}
<span id="auth-button" v-if="global.auth.orcid_enabled">
  {greeting(auth_status)}
  {#if auth_status.session == null}
	<span id="signin-button">
		<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/jpswalsh/academicons/css/academicons.min.css">
		<a class="button" href={auth_link}>
			<i class="ai ai-orcid"></i> Sign in with ORCID
		</a>
	</span>
  {:else}
	<span id="signout-button">
		<a class="button" href={"#"} on:click={signOut}>Sign out</a>
	</span>
  {/if}
</span>
{/if}