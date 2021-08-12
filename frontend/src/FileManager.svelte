<script lang="ts">
    import { onMount } from "svelte"

    import { getNotificationsContext } from "svelte-notifications"

    import { DashboardModal } from "@uppy/svelte"
    import Uppy from "@uppy/core"
    import Tus from "@uppy/tus"

    import Fa from "svelte-fa/src/fa.svelte"
    import { faTrashAlt } from "@fortawesome/free-solid-svg-icons"

    export let dataset // current local state of dataset

    let uppy = null // uppy object
    let showUppy: boolean = false // visibility toggle
    let tusd_endpoint: string = "" // URL for tus file upload (given out from server)

    // for showing notifications
    const { addNotification } = getNotificationsContext()

    // setInterval jobs waiting for checksum
    let checksumPollJobs = new Map()

    /** Reject uploads with existing and forbidden file names. */
    function checkNewFilename(filename: string) {
        if (filename in dataset.files) {
            let msg = `File named ${filename} already in dataset!`
            console.log("ERROR: " + msg)
            uppy.info(msg, "error", 3000)
            return false
        }
        //TODO: check forbidden file patterns (i.e. with schema "false")
    }

    /** Handle successful uppy upload of given filename. */
    function uploadSuccess(file: string) {
        // reflect addition of the new file in dataset
        dataset.files[file] = { checksum: null, meta: null }

        // notify
        let msg = `Upload of ${file} complete!`
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

    onMount(async () => {
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
</script>

<p>Dataset/</p>

{#each Object.entries(dataset.files) as [file, fileInfo]}
    <p>
        {file} <small>{fileInfo.checksum}</small>
        <button on:click={() => deleteFile(file)}><Fa icon={faTrashAlt} /></button>
    </p>
{/each}

{#if uppy}
    <button
        on:click={() => {
            showUppy = !showUppy
        }}>Upload files</button
    >
    <DashboardModal {uppy} plugins={[]} open={showUppy} />
{/if}

<style global>
    @import "@uppy/core/dist/style.css";
    @import "@uppy/dashboard/dist/style.css";
</style>
