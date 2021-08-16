<script lang="ts">
    import { JSONEditor, createAjvValidator } from "svelte-jsoneditor"
    import Fa from "svelte-fa/src/fa.svelte"
    import { faSave } from "@fortawesome/free-solid-svg-icons"

    export let dataset // from parent Dataset component
    export let selectedFile // from sibling FileManager component

    const validator = createAjvValidator(true) //TODO: add refs list

    // current metadata stored in dataset (must be synchronized to server)
    let savedMetadata
    $: savedMetadata = selectedFile
        ? dataset.files[selectedFile].metadata
        : dataset.metadata

    // the current metadata value, not necessarily synchronized to the server yet
    // this is our current "local state"
    let jsonMetadata

    // json stored in JSONEditor component
    let editorJson

    // is there a difference of stored and edited metadata? (modulo null/undefined)
    // export to outside to e.g. prevent leaving page?
    export let unsavedChanges: boolean = false
    $: unsavedChanges = savedMetadata != jsonMetadata

    // toggle between form and editor view
    let formView: boolean = false

    function saveMetadata() {
        if (selectedFile) dataset.files[selectedFile] = jsonMetadata
        else dataset.metadata = jsonMetadata
    }

    /** Get updates of JSON metadata. */
    function editorMetadataChanged(content) {
        console.log(content)
        let newJson = content.json
        if (!newJson) {
            try {
                newJson = JSON.parse(content.text)
            } catch (err) {
                // invalid JSON or empty string -> we interpret this as null
                newJson = null
            }
        }
        jsonMetadata = newJson
        console.log(savedMetadata, jsonMetadata, unsavedChanges)
    }

    /** switch between the views, (re-)initialize objects. */
    function setFormView(form: boolean) {
        if (!form) {
            editorJson = jsonMetadata
        } else {
            //TODO reinit form
        }
        formView = form
    }
</script>

<span style="display: flex; margin-bottom: 10px;">
    <h4>{selectedFile ? `Metadata of ${selectedFile}` : "Dataset Metadata"}</h4>
    <button disabled={!unsavedChanges} style="margin-left: 10px;" on:click={saveMetadata}
        ><Fa icon={faSave} /></button>
    <span style="margin-left: 10px;" />
    <button on:click={() => setFormView(true)} disabled={formView}>Form</button>
    <button on:click={() => setFormView(false)} disabled={!formView}>Editor</button>
</span>

<div>
    {#if formView}
        TODO
    {:else}
        <JSONEditor bind:json={editorJson} onChange={editorMetadataChanged} {validator} />
    {/if}
</div>

<style>
</style>
