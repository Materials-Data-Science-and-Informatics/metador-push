<script lang="ts">
    import { createEventDispatcher } from "svelte"
    import { onMount } from "svelte"

    import Fa from "svelte-fa/src/fa.svelte"
    import { faSave } from "@fortawesome/free-solid-svg-icons"

    import { JSONEditor, createAjvValidator } from "svelte-jsoneditor"

    const validator = createAjvValidator(true) //TODO: add refs list

    const dispatch = createEventDispatcher() // for sending events

    // ----
    // props in:
    export let selectedFile: null | string
    export let modified: boolean
    // props out:
    export let editorMetadata
    // ----

    let jsonEditor // reference to component
    let formView: boolean = false // toggle between form and editor view

    /** Get updates of JSON metadata. */
    function editorMetadataChanged(content) {
        //console.log(content)

        // depending on tree or code view we get text or json object...
        let newJson = content.json
        if (!newJson) {
            try {
                newJson = JSON.parse(content.text)
            } catch (err) {
                // invalid JSON or empty string -> we interpret this as null
                newJson = null
            }
        }
        const old = Object.assign({}, editorMetadata) // shallow copy
        editorMetadata = newJson
        // console.log(old, editorMetadata)
        if (old != editorMetadata) {
            dispatch("modified", selectedFile)
        }
    }

    /** Tell parent the user requests to save metadata. */
    function pushMeta() {
        dispatch("save", editorMetadata)
    }

    onMount(() => {
        if (!editorMetadata) {
            jsonEditor.setText("") // don't show "null" metadata
        }
    })
</script>

<span style="display: flex; margin-bottom: 10px;">
    <h4>{selectedFile ? `Metadata of ${selectedFile}` : "Dataset Metadata"}</h4>
    <button disabled={!modified} style="margin-left: 10px;" on:click={pushMeta}
        ><Fa icon={faSave} /></button>
    <span style="margin-left: 10px;" />
    <button on:click={() => (formView = true)} disabled={formView}>Form</button>
    <button on:click={() => (formView = false)} disabled={!formView}>Editor</button>
</span>

<div class:hidden={formView}>
    <JSONEditor
        bind:json={editorMetadata}
        bind:this={jsonEditor}
        onChange={editorMetadataChanged}
        {validator} />
</div>

<style>
    .hidden {
        display: none !important;
    }
</style>
