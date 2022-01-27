<script lang="ts">
    import { onMount, createEventDispatcher } from "svelte"
    import { navigate } from "svelte-navigator"

    import {
        fetchJSON,
        getNotifier,
        getSchemaNameFor,
        getFirstMatchingPattern,
    } from "./util"
    import type { Dataset, FileInfos } from "./util"

    import { DashboardModal } from "@uppy/svelte"
    import Uppy from "@uppy/core"
    import type { UppyFile, UppyOptions } from "@uppy/core"
    import Tus from "@uppy/tus"

    import Fa from "svelte-fa"
    import {
        faTrashAlt,
        faUpload,
        faPencilAlt,
        faCheckDouble,
        faDownload,
    } from "@fortawesome/free-solid-svg-icons"

    import { saveAs } from "file-saver"

    // props:
    export let dataset: Dataset // current local state of dataset
    export let selectedFile: string | null = null // currently selected file
    export let unsavedChanges: boolean
    export let hasFiles: boolean

    // local vars:
    let uppy = null // uppy object
    let showUppy: boolean = false // visibility toggle
    let tusd_endpoint: string = "" // URL for tus file upload (given out from server)

    // setInterval jobs waiting for checksum of new uploads
    let checksumPollJobs = new Map()
    const checksumFilename: string = dataset.checksumTool + "s.txt"

    const dispatch = createEventDispatcher() // for sending events
    const notify = getNotifier() // for showing notifications

    onMount(async () => {
        // before we can upload with uppy, we need the tusd URL from the server
        await fetchJSON("/tusd-endpoint").then((str: string) => (tusd_endpoint = str))

        const uppyConf: UppyOptions = {
            meta: { dataset: dataset.id },
            onBeforeFileAdded: beforeFileAdded,
        }
        uppy = new Uppy(uppyConf)
            .use(Tus, { endpoint: tusd_endpoint })
            .on("upload-success", (file: UppyFile) => uploadSuccess(file.name))
    })

    /** Handle uppy event (user selected a file). */
    function beforeFileAdded(file: UppyFile): UppyFile | boolean {
        const ret = checkNewFilename(file.name)
        if (ret) {
            file.name = ret
            return file
        }
        return false
    }

    /** Reject uploads with and renames to existing and forbidden file names. */
    function checkNewFilename(filename: string) {
        if (filename in dataset.files) {
            notify(`File named ${filename} already in dataset!`, "danger")
            return false
        }

        const pr = dataset.profile
        const fileSchema = pr.schemas[getSchemaNameFor(pr, filename)]
        if (fileSchema == false) {
            let pat = getFirstMatchingPattern(dataset.profile.patterns, filename)
            let msg = `Filename does not match any allowed name pattern!`
            if (pat) {
                msg = `Filename ${pat.pattern} matches a forbidden pattern!`
            }
            notify(msg, "danger")
            return false
        }
        return filename
    }

    /** Handle successful uppy upload of given filename. */
    function uploadSuccess(file: string) {
        // reflect addition of the new file in dataset
        dataset.files[file] = { checksum: null, metadata: null }
        hasFiles = true
        notify(`Upload of ${file} complete`)

        // start polling for the checksum
        checksumPollJobs.set(file, setInterval(getChecksum, 2000, file))
    }

    /** update the checksum for given file, if available. */
    async function getChecksum(filename: string) {
        fetchJSON(`/api/datasets/${dataset.id}/files/${filename}/checksum`).then(
            (chksum) => {
                if (chksum) {
                    dataset.files[filename].checksum = chksum as string
                    clearInterval(checksumPollJobs.get(filename))
                    checksumPollJobs.delete(filename)
                }
            }
        )
    }

    /** Delete file or dataset on the server and reflect change in UI. */
    async function deleteFile(file: string | null) {
        let msg = "Are you sure that you want to delete "
        msg += file ? file : "this dataset"
        msg += "? This cannot be undone!"
        if (!confirm(msg)) return

        let url = `/api/datasets/${dataset.id}`
        if (file) {
            url += `/files/${file}`
        }

        await fetchJSON(url, { method: "DELETE" })
            .then(() => {
                if (file) {
                    // just remove a file
                    delete dataset.files[file]
                    dataset.files = dataset.files

                    // if we deleted the current one, focus dataset root
                    if (selectedFile == file) {
                        selectedFile = null
                        dispatch("select", { file: null })
                    }

                    dispatch("delete", { file: file })
                } else {
                    // dataset deleted -> back to homepage
                    navigate("/")
                    dataset = null
                }

                notify(`${file ? file : "Dataset"} deleted`)
                hasFiles = dataset.files.length > 0
            })
            .catch(() => {
                notify(`Cannot delete ${file ? file : dataset.id}!`, "danger")
            })
    }

    /** Try to rename a file (if it does not violate anything). */
    async function renameFile(e: Event, file: string) {
        const target = e.target as HTMLInputElement
        const newName: string = target.value
        //console.log("trying rename: " + file + " -> " + newName)

        const sucMsg: string = `Renamed "${file}" to "${newName}"`
        const errMsg: string = `Cannot rename "${file}" to "${newName}"!`
        if (newName == "" || !checkNewFilename(newName)) {
            notify(errMsg, "danger")
            target.value = file // reset change
            return
        }

        // try to rename on server
        const renameUrl = `/api/datasets/${dataset.id}/files/${file}/rename-to/${newName}`
        await fetchJSON(renameUrl, { method: "PATCH" })
            .then(() => {
                // perform local rename
                dataset.files[newName] = dataset.files[file]
                delete dataset.files[file]

                let selectedRenamed = false
                if (selectedFile == file) {
                    selectedFile = newName
                    selectedRenamed = true
                }
                dispatch("rename", { file: file, to: newName })
                if (selectedRenamed) {
                    dispatch("select", { file: newName })
                }

                notify(sucMsg)
            })
            .catch(() => {
                notify(errMsg, "danger")
                target.value = file // reset change
            })
    }

    /** Open metadata edit view for file or dataset. */
    async function openMetadata(filename?: string | null) {
        if (filename == selectedFile && !unsavedChanges) {
            return //nothing to do
        }

        let proceed: boolean = true
        if (unsavedChanges) {
            proceed = confirm("All unsaved changes will be lost! Are you sure?")
        }
        if (proceed) {
            selectedFile = filename
            dispatch("select", { file: selectedFile })
        }
    }

    /** Compute a checksum file from the JSON object that can be used for verification. */
    function computeChecksums(files: FileInfos): string {
        let content: string = ""
        for (const [filename, info] of Object.entries(files)) {
            content += info.checksum + "  " + filename + "\n"
        }
        return content
    }

    let checksumFileContent: string = ""
    $: checksumFileContent = computeChecksums(dataset.files)

    /** Let user download checksums as a text file. */
    function saveChecksums() {
        const chksumArea = document.getElementById("checksums") as HTMLTextAreaElement
        var checksumFile = new Blob([chksumArea.value], {
            type: "text/plain;charset=utf-8",
        })
        saveAs(checksumFile, checksumFilename)
    }

    /** Helper to prevent TypeScript errors. */
    function selectAllText(el: EventTarget) {
        const elem = el as HTMLTextAreaElement
        elem.select()
    }

    /** Helper function to mark currently selected file edit button green/red. */
    function editButtonClass(btnFile: string | null, sel: string | null, uns: boolean) {
        let str = "tooltip-left"
        if (sel === btnFile) {
            if (uns) {
                str += " error"
            } else {
                str += " success"
            }
        }
        return str
    }
</script>

<span style="display: flex; margin-bottom: 10px;">
    <h4 style="flex-grow: 1;">Dataset/</h4>
    {#if uppy}
        <DashboardModal {uppy} plugins={[]} open={showUppy} />
        <button
            class="tooltip-left"
            data-tooltip="Upload files"
            on:click={() => (showUppy = !showUppy)}>
            <Fa icon={faUpload} />
        </button>
    {/if}
    <label data-tooltip="File checksums" for="modal_checksums" class="button tooltip-left"
        ><Fa icon={faCheckDouble} /></label>
    <div class="modal">
        <input id="modal_checksums" type="checkbox" />
        <label for="modal_checksums" class="overlay" />
        <article style="width: 50%; height: 50%;">
            <header>
                <h3>{checksumFilename}</h3>
                <label for="modal_checksums" class="close">&times;</label>
            </header>
            <section
                class="content"
                style="display: flex; flex-direction: column; height: 85%; ">
                <div style="height: 100%;">
                    <textarea
                        id="checksums"
                        style="font-family: monospace; resize: none; box-sizing: border-box; height: 100%;"
                        readonly={true}
                        on:click={(e) => selectAllText(e.target)}
                        >{checksumFileContent}</textarea>
                </div>
                <div style="float: right;">
                    <button
                        for="modal_checksums"
                        data-tooltip="download"
                        class="tooltip-right"
                        on:click={saveChecksums}>
                        <Fa icon={faDownload} /></button>
                </div>
            </section>
        </article>
    </div>
    <button
        class="tooltip-left"
        data-tooltip="Delete dataset"
        on:click={() => deleteFile(null)}><Fa icon={faTrashAlt} /></button>
    <button
        class={editButtonClass(null, selectedFile, unsavedChanges)}
        on:click={() => openMetadata(null)}>
        <Fa icon={faPencilAlt} /></button>
</span>

{#each Object.keys(dataset.files) as file (file)}
    <div style="margin-left: 20px;">
        <div style="margin-bottom: 10px;">
            <div style="display: flex;">
                <input
                    type="text"
                    style="flex-grow: 1;"
                    value={file}
                    disabled={!dataset.files[file].checksum ||
                        (selectedFile == file && unsavedChanges)}
                    on:change={(e) => renameFile(e, file)} />
                <button
                    style="margin-top: 0px;"
                    class="tooltip-left"
                    data-tooltip="Delete file"
                    on:click={() => deleteFile(file)}><Fa icon={faTrashAlt} /></button>
                <button
                    style="margin-top: 0px;"
                    class={editButtonClass(file, selectedFile, unsavedChanges)}
                    on:click={() => openMetadata(file)}>
                    <Fa icon={faPencilAlt} /></button>
            </div>
        </div>
    </div>
{/each}

<style global>
    @import "@uppy/core/dist/style.css";
    @import "@uppy/dashboard/dist/style.css";
</style>
