// D3.js script to visualize the family tree

document.addEventListener('DOMContentLoaded', () => {
    console.log('[DEBUG] DOMContentLoaded event fired.');

    const container = document.getElementById('visualization-container');
    if (!container) {
        console.error('Visualization container not found');
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;
    console.log(`[DEBUG] Container dimensions: width=${width}, height=${height}`);

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g');
    console.log('[DEBUG] SVG and G elements created.');

    const zoom = d3.zoom()
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
            g.attr('transform', event.transform);
        });
    svg.call(zoom);

    const nodeSize = 32;

    g.append('defs').append('clipPath')
        .attr('id', 'clip-circle')
        .append('circle')
        .attr('r', nodeSize / 2);

    d3.json('data.json').then(data => {
        console.log('[DEBUG] data.json loaded successfully:', data);

        const links = data.edges.map(d => ({ source: d.from, target: d.to, type: d.type }));
        const nodes = data.nodes;

        // Find maxGeneration from pre-calculated data
        let maxGeneration = 0;
        nodes.forEach(node => {
            if (node.generation > maxGeneration) {
                maxGeneration = node.generation;
            }
        });
        console.log("[DEBUG] Max Generation from data:", maxGeneration);

        const levelHeight = 180;
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).strength(0.4).distance(100))
            .force("charge", d3.forceManyBody().strength(-600))
            .force("collide", d3.forceCollide(nodeSize + 10))
            .force("x", d3.forceX(width / 2).strength(0.02))
            .force("y", d3.forceY(d => height - 100 - (d.generation * levelHeight)).strength(d => d.generation === -1 ? 0 : 1));

        const link = g.append("g").attr("class", "links").selectAll("line").data(links).enter().append("line").attr("class", d => `link ${d.type}`);
        const node = g.append("g").attr("class", "nodes").selectAll("g").data(nodes).enter().append("g").attr("class", "node").call(d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended));

        node.each(function(d) {
            const group = d3.select(this);
            if (d.photo_path) {
                group.append("image").attr("xlink:href", d.photo_path).attr("clip-path", "url(#clip-circle)").attr("x", -nodeSize / 2).attr("y", -nodeSize / 2).attr("width", nodeSize).attr("height", nodeSize);
            } else {
                group.append("circle").attr("r", nodeSize / 2).attr("fill", "#ccc").attr("stroke", "#fff").attr("stroke-width", "1.5px");
            }
        });

        node.append("text").text(d => d.name).attr("y", (nodeSize / 2) + 14).attr("class", "label");

        simulation.on("tick", () => {
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y).attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            node.attr("transform", d => `translate(${d.x},${d.y})`);
        });

        function dragstarted(event, d) { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }
        function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
        function dragended(event, d) { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }

        // --- CONTROL PANEL LOGIC ---
        let searchResults = [];
        let currentSearchResultIndex = 0;

        function resetView() {
            const bounds = g.node().getBBox();
            const fullWidth = bounds.width;
            const fullHeight = bounds.height;
            const midX = bounds.x + fullWidth / 2;
            const midY = bounds.y + fullHeight / 2;
            if (fullWidth === 0 || fullHeight === 0) return; // nothing to fit
            const scale = 0.9 / Math.max(fullWidth / width, fullHeight / height);
            const translate = [width / 2 - scale * midX, height / 2 - scale * midY];
            const transform = d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale);
            svg.transition().duration(750).call(zoom.transform, transform);
        }

        d3.select('#zoom-in').on('click', () => svg.transition().duration(250).call(zoom.scaleBy, 1.3));
        d3.select('#zoom-out').on('click', () => svg.transition().duration(250).call(zoom.scaleBy, 1 / 1.3));
        d3.select('#reset-zoom').on('click', resetView);
        
        d3.select('#search-button').on('click', handleSearch);
        d3.select('#search-input').on('keydown', (event) => { if (event.key === 'Enter') handleSearch(); });
        d3.select('#search-next').on('click', () => navigateSearchResults(1));
        d3.select('#search-prev').on('click', () => navigateSearchResults(-1));

        function handleSearch() {
            const searchTerm = d3.select('#search-input').property('value').toLowerCase();
            node.classed('highlighted', false);

            if (!searchTerm) {
                searchResults = [];
                updateSearchUI();
                return;
            }

            searchResults = nodes.filter(d => d.name.toLowerCase().includes(searchTerm));
            currentSearchResultIndex = 0;
            
            if (searchResults.length > 0) {
                node.filter(d => searchResults.includes(d)).classed('highlighted', true);
                focusOnSearchResult();
            } else {
                alert('No person found with that name.');
            }
            updateSearchUI();
        }

        function navigateSearchResults(direction) {
            if (searchResults.length === 0) return;
            currentSearchResultIndex += direction;
            if (currentSearchResultIndex >= searchResults.length) {
                currentSearchResultIndex = 0; // Wrap around to the start
            }
            if (currentSearchResultIndex < 0) {
                currentSearchResultIndex = searchResults.length - 1; // Wrap around to the end
            }
            focusOnSearchResult();
        }

        function focusOnSearchResult() {
            const targetNode = searchResults[currentSearchResultIndex];
            const transform = d3.zoomIdentity.translate(width / 2, height / 2).scale(1.5).translate(-targetNode.x, -targetNode.y);
            svg.transition().duration(750).call(zoom.transform, transform);
            updateSearchUI();
        }

        function updateSearchUI() {
            const count = searchResults.length;
            const countDisplay = d3.select('#search-count');
            const prevButton = d3.select('#search-prev');
            const nextButton = d3.select('#search-next');

            if (count > 1) {
                countDisplay.style('display', 'inline').text(`${currentSearchResultIndex + 1} of ${count}`);
                prevButton.style('display', 'inline-block');
                nextButton.style('display', 'inline-block');
            } else {
                countDisplay.style('display', 'none');
                prevButton.style('display', 'none');
                nextButton.style('display', 'none');
            }
        }

        // Set the initial view
        setTimeout(resetView, 1500);

    }).catch(error => {
        console.error('[DEBUG] Critical error loading or processing data.json:', error);
    });
});