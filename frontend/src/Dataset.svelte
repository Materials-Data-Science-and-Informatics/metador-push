<script lang="ts">
    import { onMount } from "svelte"
    import { navigate } from "svelte-navigator"
    import FileManager from "./FileManager.svelte"
    import MetadataEditor from "./MetadataEditor.svelte"
    import ProfileViewer from "./ProfileViewer.svelte"
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

    async function submitDataset() {
        let msg = "Are you sure you want to submit the dataset? "
        msg += "After submission you cannot access or edit it anymore!"
        if (!confirm(msg)) return

        await fetchJSON(`/api/datasets/${dataset.id}`, { method: "PUT" })
            .then(() => {
                notify("Dataset submission complete!")
                navigate(`/complete/${dataset.id}`)
            })
            .catch((err) => {
                console.log(err)
                notify(
                    "Cannot submit dataset, check that the metadata is valid!",
                    "danger"
                )
            })
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

    /** Format date to local format (without sec/ms). */
    function expiryDateStr(): string {
        const date = new Date(dataset.expires)
        let ret = date.toLocaleDateString(undefined, {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        })
        ret += " "
        ret += date.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
        })
        return ret
    }

    /** Completion of dataset is urgent if it has less than 1h. */
    function completionUrgent(): boolean {
        const date = new Date(dataset.expires)
        return parseInt((date - Date.now()) / 1000) < 3600
    }
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
        <span style="margin-top: 20px"
            ><b>Profile:</b> <ProfileViewer profile={dataset.profile} /></span>
        <span style="margin-top: 20px">
            <b>To complete until:</b>
            <span class:urgent={completionUrgent()}>{expiryDateStr()}</span>
        </span>
        <span style="width:30%;" />
        <button disabled={modified} on:click={submitDataset}><h3>Submit</h3></button>
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
    .urgent {
        font-weight: bold;
        color: red;
    }
</style>
