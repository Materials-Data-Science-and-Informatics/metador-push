<script lang="ts">
    import { onMount } from "svelte"
    import FileManager from "./FileManager.svelte"
    import MetadataEditor from "./MetadataEditor.svelte"
    import { getNotifier } from "./util"

    const notify = getNotifier() // for showing notifications

    export let dsId: string // passed from parent, we will try to load it

    let notFound = false // set to true on failure to load given dsId

    // all information about the dataset
    // initialized on mount, assertion: always in sync with server
    //TODO: add expires field in backend
    let dataset

    let selectedFile // from FileManager component
    let editorMetadata
    let reloadEditor = {}

    /** When a user selects a new file/the root, get the metadata stored in the dataset */
    function getMetadata() {
        if (dataset) {
            if (selectedFile) {
                editorMetadata = dataset.files[selectedFile].metadata
            } else {
                editorMetadata = dataset.rootMeta
            }
            modified = false
            reloadEditor = {}
        }
    }

    let modified = false // from MetadataEditor component

    /** Handle event that the metadata JSON has been modified. */
    function setModified(e) {
        // check that the message comes from the currently selected file
        // otherwise we sometimes get an old event from previous selected file
        if (e.detail == selectedFile) {
            modified = true
        }
    }

    /** Handle event that user pressed save. Store the updated metadata in the dataset. */
    async function saveMetadata(e) {
        const meta = e.detail

        let url = `/api/datasets/${dataset.id}`
        if (selectedFile) {
            url += `/files/${selectedFile}`
        }
        url += "/meta"

        const entityStr = selectedFile ? selectedFile : "dataset"
        await fetch(url, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(meta),
        }).then((r) => {
            if (r.ok) {
                if (selectedFile) {
                    dataset.files[selectedFile].metadata = e.detail
                } else {
                    dataset.rootMeta = e.detail
                }
                modified = false

                const msg = `Metadata for ${entityStr} saved`
                console.log(msg)
                notify(msg)
            } else {
                let msg = `Cannot save metadata for ${entityStr}!`
                console.log(msg)
                notify(msg, "danger")
            }
        })
    }

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
                    getMetadata()
                    reloadEditor = {}
                }
            })
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
            <FileManager
                bind:dataset
                bind:selectedFile
                on:select={getMetadata}
                unsavedChanges={modified} />
        </div>
        <div id="file-metadata">
            {#key reloadEditor}
                <MetadataEditor
                    {selectedFile}
                    {editorMetadata}
                    {modified}
                    profile={dataset.profile}
                    on:save={saveMetadata}
                    on:modified={setModified} />
            {/key}
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
        flex: 1;
        height: 90vh;
        border-right: 1px solid;
        padding-right: 10px;
        overflow: auto;
    }
    #file-metadata {
        flex: 3;
        padding-left: 10px;
        height: 90vh;
        overflow: auto;
    }
</style>
