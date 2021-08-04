<script>
	import { DashboardModal } from '@uppy/svelte'
	import Uppy from '@uppy/core'

	export let dataset;

	let uppy = new Uppy({meta: {
		'Dataset': dataset.id
	}});

	let showUppy = false;
	const toggleUppy = () => { showUppy = !showUppy; }
</script>
<style global>
	@import '@uppy/core/dist/style.css';
	@import '@uppy/dashboard/dist/style.css';
</style>

<button on:click={toggleUppy}>Upload files</button>
<DashboardModal uppy={uppy} plugins={[]} open={showUppy}/>
