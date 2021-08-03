<script lang="ts">
	import { Router, Link, Route } from "svelte-navigator";

	import AuthButton from "./AuthButton.svelte";
	import Message from "./Message.svelte";
	import Dataset from "./Dataset.svelte";
	import DatasetSelection from "./DatasetSelection.svelte";
	import { fetchJSON } from "./util";

	fetchJSON('/site-base');

	export let url = "";

	let userSession = null; //current session (for conditional rendering)

/*
	import { Dashboard } from '@uppy/svelte'
	import Uppy from '@uppy/core'
	let uppy = new Uppy();
*/
</script>

<style global>
@import '@uppy/core/dist/style.css';
@import '@uppy/dashboard/dist/style.css';
</style>

<Router url="{url}">
<header>
	<nav>
		<Link to="/"
		class="brand"
		data-tooltip="Metadata Enrichment and Transmission Assistance for Digital Objects in Research">
		Metador
		</Link>

		<span style="position: relative; top: 25%;">
			<i><small>The metadata-aware mailbox for research data.</small></i>
		</span>

		<div class="menu">
			<AuthButton bind:userSession />
		</div>
	</nav>
<!-- <div style="height:70px"></div> -->
</header>

<main style="margin: 4% 2% 1% 2%;"> 
	<!-- <Dashboard uppy={uppy} plugins={[]} /> -->

	<Route path="/"><DatasetSelection {userSession}/></Route>
	<Route path="/signout">
	<Message html="<h4>You have successfully signed out!</h4>" />
	</Route>

	<Route path="dataset/:id" let:params><Dataset dsId={params.id} /></Route>
</main>

<footer>
  <!-- What to put here? -->
</footer>
</Router>
