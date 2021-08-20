<script lang="ts">
    import { Link, navigate } from "svelte-navigator"
    import { fetchJSON } from "./util"

    /** Create a new dataset based on given profile and go to its view. */
    async function newDataset(profile: string) {
        fetchJSON("/api/datasets?profile=" + profile, { method: "POST" })
            .then((dsId) => {
                navigate("/datasets/" + dsId) //redirect to new dataset
            })
            .catch((err) => {
                console.log("ERROR: ", err)
            })
    }

    // type coercions to use in templating to prevent TypeScript errors
    const retStringArray = (val: any) => val as Promise<string[]>
    const retStringMap = (val: any) =>
        val as Promise<{ [profile: string]: { title: string; description: string } }>
</script>

<div class="flex three">
    <div />
    <h3>Create a new submission...</h3>
    <div />

    <div />
    <div>
        {#await retStringMap(fetchJSON("/api/profiles"))}
            Loading profile info...
        {:then pinfos}
            {#each Object.entries(pinfos) as [pId, { title, description }]}
                <Link to="#">
                    <span class="button stack" on:click={() => newDataset(pId)}>
                        <b>{title}</b> <br /> <small>{description}</small>
                    </span>
                </Link>
            {/each}
        {/await}
    </div>
    <div />

    {#await retStringArray(fetchJSON("/api/datasets"))}
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
