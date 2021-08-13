<script lang="ts">
    import { onMount } from "svelte"
    import { navigate } from "svelte-navigator"

    import { getNotificationsContext } from "svelte-notifications"

    import { DashboardModal } from "@uppy/svelte"
    import Uppy from "@uppy/core"
    import Tus from "@uppy/tus"

    import Fa from "svelte-fa/src/fa.svelte"
    import {
        faTrashAlt,
        faUpload,
        faPencilAlt,
        faCheckDouble,
        faDownload,
    } from "@fortawesome/free-solid-svg-icons"

    import { saveAs } from "file-saver"
    export let dataset // current local state of dataset

    let uppy = null // uppy object
    let showUppy: boolean = false // visibility toggle
    let tusd_endpoint: string = "" // URL for tus file upload (given out from server)

    // for showing notifications
    const { addNotification } = getNotificationsContext()

    // setInterval jobs waiting for checksum of new uploads
    let checksumPollJobs = new Map()
    const checksumFilename: string = dataset.checksumTool + "s.txt"

    onMount(async () => {
        // before we can upload with uppy, we need the tusd URL from the server
        await fetch("/tusd-endpoint")
            .then((r) => r.json())
            .then((str) => (tusd_endpoint = str))

        uppy = new Uppy({
            meta: { dataset: dataset.id },
            onBeforeFileAdded: (file) => checkNewFilename(file.name),
        })
            .use(Tus, { endpoint: tusd_endpoint })
            .on("upload-success", (file) => uploadSuccess(file.name))
    })

    /** Reject uploads with existing and forbidden file names. */
    function checkNewFilename(filename: string) {
        if (filename in dataset.files) {
            let msg = `File named ${filename} already in dataset!`
            console.log("ERROR: " + msg)
            uppy.info(msg, "error", 3000)
            return false
        }
        return filename
        //TODO: check forbidden file patterns (i.e. with schema "false")
    }

    /** Handle successful uppy upload of given filename. */
    function uploadSuccess(file: string) {
        // reflect addition of the new file in dataset
        dataset.files[file] = { checksum: null, meta: null }

        // notify
        let msg = `Upload of ${file} complete`
        console.log(msg)
        addNotification({
            text: msg,
            removeAfter: 3000,
            position: "bottom-center",
        })

        // start polling for the checksum
        checksumPollJobs.set(file, setInterval(getChecksum, 2000, file))
    }

    /** update the checksum for given file, if available. */
    async function getChecksum(filename: string) {
        await fetch(`/api/datasets/${dataset.id}/files/${filename}/checksum`)
            .then((r) => r.json())
            .then((chksum) => {
                if (chksum) {
                    dataset.files[filename].checksum = chksum
                    clearInterval(checksumPollJobs.get(filename))
                    checksumPollJobs.delete(filename)
                }
            })
    }

    /** Delete file on the server and remove in the view. */
    async function deleteFile(file: string) {
        await fetch(`/api/datasets/${dataset.id}/files/${file}`, {
            method: "DELETE",
        }).then((r) => {
            if (r.ok) {
                delete dataset.files[file]
                dataset.files = dataset.files

                let msg = `File ${file} deleted`
                console.log(msg)
                addNotification({
                    text: msg,
                    removeAfter: 3000,
                    position: "bottom-center",
                })
            } else {
                let msg = `Cannot delete ${file}!`
                console.log(msg)
                addNotification({
                    text: msg,
                    removeAfter: 3000,
                    type: "danger",
                    position: "bottom-center",
                })
            }
        })
    }

    async function deleteDataset() {
        await fetch(`/api/datasets/${dataset.id}`, {
            method: "DELETE",
        }).then((r) => {
            if (r.ok) {
                navigate("/")

                let msg = `Dataset ${dataset.id} deleted`
                console.log(msg)
                addNotification({
                    text: msg,
                    removeAfter: 3000,
                    position: "bottom-center",
                })
                dataset = null
            } else {
                let msg = `Cannot delete dataset ${dataset.id}!`
                console.log(msg)
                addNotification({
                    text: msg,
                    removeAfter: 3000,
                    type: "danger",
                    position: "bottom-center",
                })
            }
        })
    }

    /** Try to rename a file (if it does not violate anything). */
    async function renameFile(e, file: string) {
        const newName: string = e.target.value
        console.log("trying rename: " + file + " -> " + newName)

        const sucMsg: string = `Renamed "${file}" to "${newName}"`
        const errMsg: string = `Cannot rename "${file}" to "${newName}"!`

        if (e.target.value == "" || !checkNewFilename(newName)) {
            addNotification({
                text: errMsg,
                removeAfter: 3000,
                type: "danger",
                position: "bottom-center",
            })
            e.target.value = file // reset change
            return
        }

        // try to rename on server
        await fetch(`/api/datasets/${dataset.id}/files/${file}/rename-to/${newName}`, {
            method: "PATCH",
        }).then((r) => {
            if (r.ok) {
                // perform local rename
                dataset.files[e.target.value] = dataset.files[file]
                delete dataset.files[file]

                addNotification({
                    text: sucMsg,
                    removeAfter: 3000,
                    position: "bottom-center",
                })
            } else {
                addNotification({
                    text: errMsg,
                    removeAfter: 3000,
                    type: "danger",
                    position: "bottom-center",
                })
                e.target.value = file // reset change
            }
        })
    }

    /** Open metadata edit view for file or dataset. */
    async function openMetadata(filename?: string) {
        alert("TODO: show metadata for " + filename)
    }

    /** Compute a checksum file from the JSON object that can be used for verification */
    function computeChecksums(files): string {
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
        var checksumFile = new Blob([document.getElementById("checksums").value], {
            type: "text/plain;charset=utf-8",
        })
        saveAs(checksumFile, checksumFilename)
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
                        readonly="true"
                        on:click={(e) => e.target.select()}
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
    <button class="tooltip-left" data-tooltip="Delete dataset" on:click={deleteDataset}
        ><Fa icon={faTrashAlt} /></button>
    <button
        class="tooltip-left"
        data-tooltip="Show/edit dataset metadata"
        on:click={() => openMetadata(null)}>
        <Fa icon={faPencilAlt} /></button>
</span>

{#each Object.entries(dataset.files) as [file, fileInfo] (file)}
    <div style="margin-left: 20px;">
        <div style="margin-bottom: 10px;">
            <div style="display: flex;">
                <input
                    type="text"
                    style="flex-grow: 1;"
                    value={file}
                    on:change={(e) => renameFile(e, file)} />
                <button
                    style="margin-top: 0px;"
                    class="tooltip-left"
                    data-tooltip="Delete file"
                    on:click={() => deleteFile(file)}><Fa icon={faTrashAlt} /></button>
                <button
                    style="margin-top: 0px;"
                    class="tooltip-left"
                    data-tooltip="Show/edit file metadata"
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
