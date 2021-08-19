<script lang="ts">
    import { onDestroy, onMount } from "svelte"

    import React from "react"
    import ReactDOM from "react-dom"

    // this design is the only one that works without any issues...
    import Form from "@rjsf/material-ui"

    const e = React.createElement

    export let schema
    export let prefill
    export let onChange

    // TODO: repackage other schemas into the current one
    // as only schema-internal $ref can be used

    let container // ref to DOM element to mount component into
    let component // ref to mounted react component instance

    // if anything goes, allow arbitrary key-value string pairs
    const anythingSchema = { additionalProperties: { type: "string" } }

    onMount(() => {
        ReactDOM.render(
            e(
                Form,
                {
                    liveValidate: true,
                    schema: schema === true ? anythingSchema : schema,
                    formData: prefill ? prefill : {}, // just initial pre-fill data
                    onChange: (e) => onChange({ json: e.formData }),
                    ref: (c) => (component = c),
                },
                e("span") // pass empty child to prevent creation of submit button
            ),
            container
        )
    })

    onDestroy(() => {
        ReactDOM.unmountComponentAtNode(container)
    })
</script>

<div bind:this={container} />
