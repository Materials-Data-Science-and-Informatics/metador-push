<script lang="ts">
    /** This component visualizes a dataset profile (patterns and schemas). */
    import { JSONEditor } from "svelte-jsoneditor"

    import type { JSONVal, Profile } from "./util"
    import { selfContainedSchema, getFirstMatchingPattern } from "./util"

    export let profile: Profile

    //name of selected schema (key in profile)
    let selected: string = profile.rootSchema

    //title shown for that schema above jsoneditor
    let selTitle: string = "dataset root"
    const defFile: string = "file (default)"

    //the actual schema to show
    export let json: JSONVal = undefined

    //the actual matching pattern for highlighting
    //undefined = no match performed, null = no match (-> fallback), otherwise pattern
    let matchPat: undefined | null | number
    //the clicked/selected pattern directly
    let selPat: undefined | null | number

    function updateMatchingPattern(e: Event) {
        const str = (e.target as HTMLInputElement).value
        if (str == "") {
            matchPat = undefined
            return
        }

        const pat = getFirstMatchingPattern(profile.patterns, str)

        const patName = pat ? pat.useSchema : ""
        const patTitle = pat ? pat.pattern : defFile
        let patIdx = profile.patterns.findIndex((el) => el == pat)
        if (patIdx < 0) {
            patIdx = null
        }

        //show corresponding JSON Schema in editor
        select(patName, patTitle, patIdx)
        //set the highlighted pattern (select unsets it before!)
        matchPat = patIdx
    }

    /** 
      Helper for setting profile schema name and title in header.
      Name maps null to rootSchema and empty string to fallbackSchema.
     */
    function select(name: null | string, title: string, sel: undefined | null | number) {
        if (name === null) {
            selected = profile.rootSchema
        } else if (name == "") {
            selected = profile.fallbackSchema
        } else {
            selected = name
        }
        json = selfContainedSchema(profile, selected)
        selTitle = title
        matchPat = undefined //user clicked pattern -> un-highlight text match
        selPat = sel
    }
</script>

<label
    class="pseudo button"
    for="modal_profile"
    style="cursor: help; margin-top: -15px; margin-bottom: -15px;">{profile.title}</label>
<div class="modal">
    <input id="modal_profile" type="checkbox" />
    <label for="modal_profile" class="overlay" />
    <article style="width: 75%; height: 75%;">
        <header>
            <h3>Profile: {profile.title}</h3>
            <label for="modal_profile" class="close">&times;</label>
        </header>
        <section
            class="content"
            style="display: flex; flex-direction: column; height: 90%; ">
            <div style="height: 100%;" class="flex three">
                <div style="display: flex; flex-direction: column; height: 80%; ">
                    <span
                        class="pseudo button"
                        class:select={selPat === undefined}
                        on:click={() => select(null, "dataset root", undefined)}>
                        dataset root metadata
                    </span>
                    <span style="border-top: 1px solid black;">
                        <b>File patterns:</b>
                    </span>
                    {#each profile.patterns as pat, i}
                        <span
                            class="pseudo button"
                            class:match={matchPat == i}
                            class:select={selPat == i}
                            style="font-family: monospace"
                            on:click={() => select(pat.useSchema, pat.pattern, i)}
                            >{pat.pattern}</span>
                    {/each}
                    <span
                        class="pseudo button"
                        class:match={matchPat === null}
                        class:select={selPat === null}
                        on:click={() => select("", defFile, null)}>
                        default
                    </span>

                    <div style="text-align: center; margin-top: 50px;">
                        For files, the first matching pattern determines the schema.
                        <br />
                        If no pattern matches, the default schema is used.
                    </div>
                    <div style="margin-top: 20px;">
                        Enter a filename to highlight the applying schema: <input
                            on:input={updateMatchingPattern} />
                    </div>
                </div>

                <div class="two-third" style="height: 95%;">
                    {#if json !== false}
                        <h4>JSON Schema for: {selTitle}</h4>
                        <JSONEditor readOnly={true} {json} />
                    {:else}
                        <h4>Forbidden Pattern</h4>
                        <div>You can not upload a file with this name.</div>
                    {/if}
                </div>
            </div>
        </section>
    </article>
</div>

<style>
    .match {
        border: 1px dashed black;
    }
    .select {
        background-color: lightgray;
    }
</style>
