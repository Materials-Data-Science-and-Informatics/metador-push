<script lang="ts">
    import { onMount } from "svelte"
    import FileManager from "./FileManager.svelte"

    export let dsId: string // passed as prop
    let notFound = false //set to true on failure to load given dsId

    // all information about the dataset
    //TODO: add expires field in backend
    let dataset // initialized on mount

    onMount(async () => {
        let ok: boolean
        await fetch("/api/datasets/" + dsId)
            .then((r) => {
                ok = r.ok
                return r.json()
            })
            .then((data) => {
                if (!ok) {
                    console.log("ERROR:")
                    console.log(data)
                    notFound = true
                } else {
                    dataset = data
                }
            })

        console.log(dataset)
    })
</script>

{#if notFound}
    <div class="flex">
        <div />
        <h3>Dataset not found!</h3>
        <div />
    </div>
{:else if !dataset}
    <h3>Loading dataset {dsId}...</h3>
{:else}
    <div class="flex">
        <h3>Dataset {dsId}</h3>
        <span>Profile: {dataset.profile.title}</span>
        <span>To complete until: {dataset.expires}</span>
    </div>
    <div id="dataset-app">
        <div id="file-list">
            <FileManager {dataset} />
        </div>
        <div id="file-metadata">
            <p>test</p>
            <p>test</p>
            <p>test</p>
        </div>
    </div>
{/if}

<style global>
    h3 {
        padding: 0 0 0 0;
    }
    #dataset-app {
        display: flex;
    }
    #file-list {
        flex: 2;
        height: 90vh;
        border-right: 1px solid;
        /* background-color: gray; */
        overflow: auto;
    }
    #file-metadata {
        flex: 10;
        height: 90vh;
        background-color: pink;
        overflow: auto;
    }
</style>
