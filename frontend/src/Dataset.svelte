<script lang="ts">
    import { onMount } from "svelte"
    import FileManager from "./FileManager.svelte"
    import MetadataEditor from "./MetadataEditor.svelte"
    import { getNotifier, fetchJSON } from "./util"
    import { selfContainedSchema, getSchemaNameFor } from "./util"
    import type { Dataset } from "./util"

    const notify = getNotifier() // for showing notifications

    // props in:
    export let dsId: string // passed from parent, we will try to load it
    // ----

    let notFound = false // is set to true on failure to load given dsId

    // all information about the dataset
    // initialized on mount, assertion: always in sync with server
    //TODO: add expires field in backend
    let dataset: Dataset

    let selectedFile: null | string // from FileManager component
    let editorMetadata: any
    let reloadEditor = {} // set this to {} again to force reload of component
    let formView = true // toggle between form and editor view

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
    function setModified(e: CustomEvent<null | string>) {
        // check that the message comes from the currently selected file
        // otherwise we sometimes get an old event from previous selected file
        if (e.detail == selectedFile) {
            modified = true
        }
    }

    function assembleSchema(selectedFile: null | string) {
        const pr = dataset.profile
        return selfContainedSchema(pr, getSchemaNameFor(pr, selectedFile))
    }

    /** Handle event that user pressed save. Store the updated metadata in the dataset. */
    async function saveMetadata(e: CustomEvent<any>) {
        const meta = e.detail

        let url = `/api/datasets/${dataset.id}`
        if (selectedFile) {
            url += `/files/${selectedFile}`
        }
        url += "/meta"

        const entityStr = selectedFile ? selectedFile : "dataset"
        const metaStr = JSON.stringify(meta)
        fetchJSON(url, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: metaStr,
        })
            .then(() => {
                if (selectedFile) {
                    dataset.files[selectedFile].metadata = meta
                } else {
                    dataset.rootMeta = meta
                }
                modified = false

                notify(`Metadata for ${entityStr} saved`)
            })
            .catch((err) => {
                console.log("ERROR:", err)
                notify(`Cannot save metadata for ${entityStr}!`, "danger")
            })
    }

    onMount(async () => {
        fetchJSON("/api/datasets/" + dsId)
            .then((data) => {
                dataset = data
                getMetadata()
                reloadEditor = {}
            })
            .catch((err) => {
                console.log("ERROR:", err)
                notFound = true
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
                    bind:formView
                    schema={assembleSchema(selectedFile)}
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
