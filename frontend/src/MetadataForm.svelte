<script lang="ts">
    /**
       Dear future maintainer,

       if you are here and wonder what the hell is going on -
       yes, this is a React component wired into a Svelte application.
       I created an abomination, may g-d have mercy on my soul...

       On a more serious note - unfortunately, as of 08/2021 there is no
       Svelte component that seemed to be even close to the functionality and maturity
       of react-jsonschema-form. Other options I seriously considered were:

       * https://github.com/jsonform/jsonform

       but this one is Bootstrap-3 only, raw JS and uses something different than ajv, and

       * https://jsonforms.io/

       which was a close competitor, but also has no official Svelte bindings.

       I wanted to have this tool working and not spend weeks writing new bindings,
       so I did what I had to do, and now React is pulled in as a dependency,
       just so I can use the most popular and mature component I could find.
       Please don't hate me.

       Feel free to improve this situation and migrate to something else.
       The new solution should be able to handle Draft 7 schemas with at least internal
       $refs and ideally also use ajv for validation.
       If the jsonschema library in the backend gets support for newer standards,
       sticking with ajv allows to easily upgrade the frontend, too.
     */

    import { onDestroy, onMount } from "svelte"

    import React from "react"
    import ReactDOM from "react-dom"

    // Materia UI design is the only theme that works without any issues...
    // Others have either "intrusive" CSS, or lack support for features, e.g.
    // "additionalProperties" producing a generic "Add item" button.
    import Form from "@rjsf/material-ui"

    // props in:
    export let schema: any //schema to validate against (must be self-contained)
    export let prefill: any //current metadata JSON to prefill the form on generation
    export let onChange: (e: any) => void //handler for form/JSON data updates

    let container: HTMLElement // ref to DOM element to mount component into

    // if schema is "true", allow arbitrary key-value string pairs
    // (by default, we would get no form at all, which is not what we want)
    const anythingSchema = { additionalProperties: { type: "string" } }

    const e = React.createElement
    onMount(() => {
        ReactDOM.render(
            e(
                Form,
                {
                    liveValidate: true,
                    noHtml5Validate: true,
                    schema: schema === true ? anythingSchema : schema,
                    formData: prefill ? prefill : {}, // just initial pre-fill data
                    onChange: onChange,
                    //ref: (c) => (component = c), // reference to React comp. instance
                },
                // pass empty child to prevent creation of submit button,
                // see e.g. rjsf Github issue #1602
                e("span")
            ),
            container
        )
    })

    onDestroy(() => {
        ReactDOM.unmountComponentAtNode(container)
    })

    //TODO: I did not find a way to trigger validation programmatically
    //(which can be done using component.setState({formData: ...})).
    //So this component is regenerated when the user changes from the Editor
    //view to this Form view. This is not elegant, but works good enough.
</script>

<div bind:this={container} />
