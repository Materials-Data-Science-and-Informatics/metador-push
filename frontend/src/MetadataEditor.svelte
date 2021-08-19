<script lang="ts">
    import { createEventDispatcher } from "svelte"
    import { onMount } from "svelte"

    import Fa from "svelte-fa/src/fa.svelte"
    import { faSave } from "@fortawesome/free-solid-svg-icons"

    import { JSONEditor, createAjvValidator } from "svelte-jsoneditor"

    import { getSchemaFor } from "./util"

    import MetadataForm from "./MetadataForm.svelte"

    const dispatch = createEventDispatcher() // for sending events

    // ----
    // props in:
    export let selectedFile: null | string
    export let modified: boolean
    export let profile
    // props out:
    export let editorMetadata
    // ----

    const schema = getSchemaFor(profile, selectedFile)
    console.log(schema)

    const validator = createAjvValidator(schema, profile.schemas)

    // references to components
    let jsonEditor
    let refreshForm = {} // set again to {} to regenerate Form component

    export let formView // toggle between form and editor view

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

    onMount(() => {
        if (!editorMetadata) {
            jsonEditor.setText("") // don't show "null" metadata
        }
    })

    function setFormView(b) {
        formView = b
        if (b) {
            refreshForm = {}
        }
    }
</script>

<span style="display: flex; margin-bottom: 10px;">
    <h4>{selectedFile ? `Metadata of ${selectedFile}` : "Dataset Metadata"}</h4>
    <button
        disabled={!modified}
        style="margin-left: 10px;"
        on:click={() => dispatch("save", editorMetadata)}><Fa icon={faSave} /></button>
    <span style="margin-left: 10px;" />
    <button on:click={() => setFormView(true)} disabled={formView}>Form</button>
    <button on:click={() => setFormView(false)} disabled={!formView}>Editor</button>
</span>

<div style="height: 90%;" class:hidden={formView}>
    <JSONEditor
        bind:json={editorMetadata}
        bind:this={jsonEditor}
        onChange={editorMetadataChanged}
        {validator} />
</div>
<div style="height: 90%;" class:hidden={!formView}>
    {#key refreshForm}
        <MetadataForm
            {schema}
            prefill={editorMetadata}
            onChange={editorMetadataChanged} />
    {/key}
</div>

<style>
    .hidden {
        display: none !important;
    }
</style>
