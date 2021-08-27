<script lang="ts">
    import { Router, Link, Route } from "svelte-navigator"
    import Notifications from "svelte-notifications"

    import AuthButton from "./AuthButton.svelte"
    import Message from "./Message.svelte"
    import Dataset from "./Dataset.svelte"
    import DatasetSelection from "./DatasetSelection.svelte"
    import { fetchJSON } from "./util"

    fetchJSON("/site-base")

    let auth_status = null //current session

    const submissionComplete = (dsId: string) => `
    <h3>Dataset submission completed</h3>
    <div>
    You just successfully submitted dataset <b>${dsId}</b>. <br />
    Please keep this ID as a reference and add it to inquiries about the dataset.
    </div>
    `
</script>

<Router url="">
    <Notifications>
        <header>
            <nav id="top-nav">
                <Link
                    to="/"
                    class="brand"
                    data-tooltip="Metadata Enrichment and Transmission Assistance for Digital Objects in Research">
                    Metador
                </Link>

                <span style="position: relative; top: 25%;">
                    <i><small>The metadata-aware mailbox for research data.</small></i>
                </span>

                <div class="menu">
                    <AuthButton bind:auth_status />
                </div>
            </nav>
        </header>

        <main id="content-wrapper">
            <Route path="/signout">
                <Message html="<h4>You have successfully signed out!</h4>" />
            </Route>
            <Route path="/complete/:id" let:params>
                <Message html={submissionComplete(params.id)} />
            </Route>
            {#if auth_status && (auth_status.session || !auth_status.orcid_enabled)}
                <Route path="/"><DatasetSelection /></Route>
                <Route path="datasets/:id" let:params><Dataset dsId={params.id} /></Route>
            {:else}
                <div style="text-align: center;">
                    <h4>Please sign in to create, edit and submit datasets!</h4>
                </div>
            {/if}
        </main>

        <footer>
            <!-- What to put here? -->
        </footer>
    </Notifications>
</Router>

<style>
    #top-nav {
        position: fixed;
        left: 0;
        right: 0;
        top: 0;
        height: 60px;
        width: 100%;
    }
    #content-wrapper {
        margin: 60px 0 0 0;
        padding: 0 10px;
        overflow-y: scroll;
        position: fixed;
        left: 0;
        top: 0;
        height: 100vh;
        width: 100%;
    }
</style>
