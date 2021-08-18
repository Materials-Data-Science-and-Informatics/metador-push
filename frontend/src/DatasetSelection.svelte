<script lang="ts">
    import { Link, navigate } from "svelte-navigator"
    import { fetchJSON } from "./util"

    /** Create a new dataset based on given profile and go to its view. */
    async function newDataset(profile: string) {
        await fetch("/api/datasets?profile=" + profile, { method: "POST" })
            .then((r) => {
                if (!r.ok) {
                    console.log("ERROR: " + r.json())
                }
                return r.json()
            })
            .then((dsId) => {
                navigate("/datasets/" + dsId) //redirect to new dataset
            })
    }
</script>

<div class="flex three">
    <div />
    <h3>Create a new submission...</h3>
    <div />

    <div />
    <div>
        {#await fetchJSON("/api/profiles")}
            Loading profile info...
        {:then pinfos}
            {#each Object.entries(pinfos) as [pId, { title, description }]}
                <Link class="button stack" to="#" on:click={() => newDataset(pId)}>
                    <b>{title}</b> <br /> <small>{description}</small>
                </Link>
            {/each}
        {/await}
    </div>
    <div />

    {#await fetchJSON("/api/datasets")}
        <div />
        <div>Loading user datasets...</div>
        <div />
    {:then dsets}
        {#if dsets.length > 0}
            <div />
            <h3>... or complete the following submissions:</h3>
            <div />

            <div />
            <div>
                {#each dsets as dsId}
                    <Link
                        class="button stack"
                        style="text-align: center;"
                        to={"/datasets/" + dsId}>
                        {dsId}
                    </Link>
                {/each}
            </div>
            <div />
        {/if}
    {/await}
</div>
