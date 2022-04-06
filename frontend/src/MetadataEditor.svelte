<script lang="ts">
    /**
       This component combines and synchronizes
       * JSONEditor (text + structural tree editor)
       * react-jsonschema-form (input form based on the schema)
     */

    import { createEventDispatcher } from "svelte"
    import { onMount } from "svelte"

    import Fa from "svelte-fa"
    import { faSave } from "@fortawesome/free-solid-svg-icons"

    import { JSONEditor, createAjvValidator } from "svelte-jsoneditor"

    import MetadataForm from "./MetadataForm.svelte"

    import type { JSONVal } from "./util"
    import { getNotifier } from "./util"

    const dispatch = createEventDispatcher() // for sending events

    const notify = getNotifier()

    // ----
    // props in:

    // toggle between form and editor view (can be used with bind)
    //(comes from parent, e.g. to preserve between file selection change)
    export let formView: boolean

    // self-contained schema and the name of the current file (or null for root metadata)
    // need that to assemble the schema into a suitable form.
    export let selectedFile: null | string
    export let schema: JSONVal

    // this component sends "modified" events up whenever the metadata changes.
    // the parent component decides whether the state is currently modified
    // based on that we enable/disable the save button (e.g. if saving succeeded)
    export let modified: boolean

    // initial value of metadata. Future changes are sent up on "save" event
    export let editorMetadata: JSONVal
    // ----

    // validator to pass into JSONEditor
    let validator = createAjvValidator(true as any)
    try {
        validator = createAjvValidator(schema as any)
    } catch (e) {
        let msg = `
        There were errors while loading the schema.
        This is a bug or misconfiguration.
        Please notify the site administrator.
        `
        notify(msg, "danger")
    }

    let jsonEditor: any // reference to JSONEditor to call methods etc.
    let jeContent: JSONVal
    $: jeContent = { json: editorMetadata }

    let refreshForm = {} // set again to {} to regenerate Form component

    /**
        Get updates of JSON metadata.
        JSONEditor passes an object with either a text or json key.
        For react-jsonschema-form updates, we repack the new value into this shape.
     */
    function editorMetadataChanged(content: { json?: JSONVal; text?: string }): void {
        // depending on tree or code view we get text or json object...
        let newJson = content.json
        if (!newJson) {
            try {
                newJson = JSON.parse(content.text)
            } catch (err) {
                // invalid JSON or empty string -> do nothing (yet)
                return
            }
        }
        const old = Object.assign({}, editorMetadata) // shallow copy
        editorMetadata = newJson

        if (old != editorMetadata) {
            jsonEditor.update(content)
            dispatch("modified", selectedFile)
        }
    }

    onMount(() => {
        if (!editorMetadata) {
            jsonEditor.set({ json: {} }) // don't accept "null" metadata
        }
    })

    function setFormView(b: boolean): void {
        formView = b
        if (b) {
            // force form regeneration when switching to form view
            refreshForm = {}
        }
    }
</script>

<div class="floating-header">
    <h4>{"Metadata of " + (selectedFile ? selectedFile : "Dataset")}</h4>
    <button
        disabled={!modified}
        style="margin-left: 10px;"
        title="save data in this form"
        on:click={() => dispatch("save", editorMetadata)}>
        <Fa icon={faSave} />
    </button>
    <span style="margin-left: 10px;" />
    <button on:click={() => setFormView(true)} disabled={formView}>Form</button>
    <button on:click={() => setFormView(false)} disabled={!formView}>Editor</button>
</div>

<div style="height: 90%;" class:hidden={formView}>
    <JSONEditor
        bind:this={jsonEditor}
        onChange={editorMetadataChanged}
        content={jeContent}
        {validator} />
</div>
<div
    style="display:flex; margin-bottom: 20px; padding-bottom:10px;"
    class:hidden={!formView}>
    {#key refreshForm}
        <MetadataForm
            {schema}
            prefill={editorMetadata}
            onChange={(e) => editorMetadataChanged({ json: e.formData })} />
    {/key}
</div>

<style>
    .hidden {
        display: none !important;
    }
    .floating-header {
        display: flex;
        flex-direction: row;
        position: sticky;
        top: 0;
        background-color: white;
        z-index: 1;
    }
</style>
