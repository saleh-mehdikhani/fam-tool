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

    // Mode management
    let currentMode = 'lineage'; // 'lineage' or 'path'
    let selectedNodes = []; // Move selectedNodes declaration to the top for proper scope
    const modeToggle = document.getElementById('mode-toggle');
    const pathStatus = document.getElementById('path-status');
    const pathStatusText = document.getElementById('path-status-text');

    function updateModeUI() {
        if (currentMode === 'lineage') {
            modeToggle.setAttribute('data-mode', 'lineage');
            modeToggle.querySelector('.mode-text').textContent = 'Lineage';
            modeToggle.title = 'Click to switch to Path Finding mode';
            pathStatus.classList.remove('show');
        } else {
            modeToggle.setAttribute('data-mode', 'path');
            modeToggle.querySelector('.mode-text').textContent = 'Path';
            modeToggle.title = 'Click to switch to Lineage mode';
            pathStatus.classList.add('show');
            updatePathStatus();
        }
    }

    function updatePathStatus() {
        if (currentMode === 'path') {
            const selectedCount = selectedNodes.length;
            if (selectedCount === 0) {
                pathStatusText.textContent = 'Select 2 people to find paths';
            } else if (selectedCount === 1) {
                pathStatusText.textContent = `Selected: ${selectedNodes[0].name}. Select 1 more.`;
            } else {
                pathStatusText.textContent = `Finding paths between ${selectedNodes[0].name} and ${selectedNodes[1].name}`;
            }
        }
    }

    modeToggle.addEventListener('click', () => {
        currentMode = currentMode === 'lineage' ? 'path' : 'lineage';
        updateModeUI();
        
        // Clear any existing selections when switching modes
        clearAllPathSelection();
        clearLineageHighlight();
    });

    // Initialize mode UI
    updateModeUI();

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

        // Add click event for lineage highlighting
        node.on("click", function(event, d) {
            event.stopPropagation();
            
            if (currentMode === 'path') {
                // In path mode, regular click selects nodes for path finding
                console.log("Path selection triggered for:", d.name);
                handlePathSelection(d);
            } else if (currentMode === 'lineage') {
                // In lineage mode, check for Ctrl/Cmd+click for path finding
                if (event.ctrlKey || event.metaKey) {
                    console.log("Path selection triggered for:", d.name);
                    handlePathSelection(d);
                } else {
                    // Regular click for lineage highlighting
                    console.log("Lineage highlighting triggered for:", d.name);
                    highlightLineage(d);
                }
            }
        });

        // Click on empty space to clear selection
         svg.on("click", function() {
             clearLineageHighlight();
             clearAllPathSelection();
         });

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

        // --- LINEAGE HIGHLIGHTING FUNCTIONS ---
        function findAncestors(personId, visited = new Set()) {
            if (visited.has(personId)) return [];
            visited.add(personId);
            
            const ancestors = [];
            const parentLinks = links.filter(link => link.target.id === personId && link.type === 'child');
            
            parentLinks.forEach(link => {
                const parentId = link.source.id;
                ancestors.push(parentId);
                // Recursively find ancestors of this parent
                ancestors.push(...findAncestors(parentId, visited));
            });
            
            return ancestors;
        }

        function findDescendants(personId, visited = new Set()) {
            if (visited.has(personId)) return [];
            visited.add(personId);
            
            const descendants = [];
            const childLinks = links.filter(link => link.source.id === personId && link.type === 'child');
            
            childLinks.forEach(link => {
                const childId = link.target.id;
                descendants.push(childId);
                // Recursively find descendants of this child
                descendants.push(...findDescendants(childId, visited));
            });
            
            return descendants;
        }

        function highlightLineage(selectedPerson) {
            // Clear any existing highlights
            clearLineageHighlight();
            
            // Find all ancestors and descendants
            const ancestors = findAncestors(selectedPerson.id);
            const descendants = findDescendants(selectedPerson.id);
            
            // Create set of all people in the lineage (including selected person)
            const lineageIds = new Set([selectedPerson.id, ...ancestors, ...descendants]);
            
            // Apply faded class to all nodes and links
            node.classed('faded', true);
            link.classed('faded', true);
            
            // Remove faded class and add lineage-highlighted class for lineage members
            node.filter(d => lineageIds.has(d.id))
                .classed('faded', false)
                .classed('lineage-highlighted', true);
            
            // Highlight the selected person specifically
            node.filter(d => d.id === selectedPerson.id)
                .classed('selected', true);
            
            // Highlight links that connect lineage members
            link.filter(d => lineageIds.has(d.source.id) && lineageIds.has(d.target.id))
                .classed('faded', false)
                .classed('lineage-highlighted', true);
        }

        function clearLineageHighlight() {
             node.classed('faded', false)
                 .classed('lineage-highlighted', false)
                 .classed('selected', false);
             link.classed('faded', false)
                 .classed('lineage-highlighted', false);
         }

         // --- PATH FINDING FUNCTIONS ---

         function handlePathSelection(selectedPerson) {
             console.log("handlePathSelection called for:", selectedPerson.name);
             console.log("Current selectedNodes:", selectedNodes.map(n => n.name));
             
             // Clear any existing lineage highlighting
             clearLineageHighlight();
             
             // Add or remove from selection
             const existingIndex = selectedNodes.findIndex(node => node.id === selectedPerson.id);
             if (existingIndex !== -1) {
                 // Remove if already selected
                 console.log("Removing from selection:", selectedPerson.name);
                 selectedNodes.splice(existingIndex, 1);
             } else {
                 // Add to selection (max 2 nodes)
                 if (selectedNodes.length >= 2) {
                     console.log("Resetting selection, starting with:", selectedPerson.name);
                     selectedNodes = [selectedPerson]; // Reset and start new selection
                 } else {
                     console.log("Adding to selection:", selectedPerson.name);
                     selectedNodes.push(selectedPerson);
                 }
             }
             
             console.log("Updated selectedNodes:", selectedNodes.map(n => n.name));
             
             // Update visual feedback
             updatePathSelectionVisual();
             
             // Update path status indicator
             updatePathStatus();
             
             // If we have exactly 2 nodes, find and highlight paths
             if (selectedNodes.length === 2) {
                 console.log("Finding paths between:", selectedNodes[0].name, "and", selectedNodes[1].name);
                 findAndHighlightShortestPaths(selectedNodes[0], selectedNodes[1]);
             } else if (selectedNodes.length === 1) {
                 console.log("One node selected, waiting for second selection");
                 // Keep the visual feedback for the selected node
             } else {
                 console.log("No nodes selected, clearing path highlight");
                 clearPathHighlight();
             }
         }

         function updatePathSelectionVisual() {
             // Clear all path selection classes
             node.classed('path-selected', false);
             
             // Apply path-selected class to selected nodes
             const selectedIds = new Set(selectedNodes.map(n => n.id));
             node.filter(d => selectedIds.has(d.id))
                 .classed('path-selected', true);
         }

         function findAndHighlightShortestPaths(startNode, endNode) {
             console.log("findAndHighlightShortestPaths called with:", startNode.name, "->", endNode.name);
             console.log("Start node ID:", startNode.id, "End node ID:", endNode.id);
             
             const paths = findAllShortestPaths(startNode.id, endNode.id);
             console.log("Found paths:", paths);
             
             if (paths.length === 0) {
                 console.log("No paths found between nodes");
                 alert('No path found between the selected persons.');
                 return;
             }
             
             console.log("Number of shortest paths found:", paths.length);
             
             // Clear existing highlights
             clearPathHighlight();
             
             // Fade all nodes and links
             node.classed('faded', true);
             link.classed('faded', true);
             
             // Collect all nodes and links in shortest paths
             const pathNodeIds = new Set();
             const pathLinkPairs = new Set();
             
             paths.forEach(path => {
                 console.log("Processing path:", path);
                 // Add all nodes in this path
                 path.forEach(nodeId => pathNodeIds.add(nodeId));
                 
                 // Add all links in this path
                 for (let i = 0; i < path.length - 1; i++) {
                     const from = path[i];
                     const to = path[i + 1];
                     pathLinkPairs.add(`${from}-${to}`);
                     pathLinkPairs.add(`${to}-${from}`); // Both directions
                 }
             });
             
             console.log("Path node IDs:", Array.from(pathNodeIds));
             console.log("Path link pairs:", Array.from(pathLinkPairs));
             
             // Highlight path nodes
             node.filter(d => pathNodeIds.has(d.id))
                 .classed('faded', false)
                 .classed('path-highlighted', true);
             
             // Highlight path links
             link.filter(d => {
                 const linkKey1 = `${d.source.id}-${d.target.id}`;
                 const linkKey2 = `${d.target.id}-${d.source.id}`;
                 return pathLinkPairs.has(linkKey1) || pathLinkPairs.has(linkKey2);
             })
                 .classed('faded', false)
                 .classed('path-highlighted', true);
             
             // Keep selected nodes visible with their special styling
             updatePathSelectionVisual();
         }

         function findAllShortestPaths(startId, endId) {
             console.log("findAllShortestPaths called with startId:", startId, "endId:", endId);
             
             // BFS to find shortest path length
             const queue = [[startId]];
             const visited = new Set();
             const allPaths = [];
             let shortestLength = Infinity;
             
             console.log("Starting BFS with queue:", queue);
             
             while (queue.length > 0) {
                 const currentPath = queue.shift();
                 const currentNode = currentPath[currentPath.length - 1];
                 
                 console.log("Processing path:", currentPath, "current node:", currentNode);
                 
                 // If path is longer than shortest found, skip
                 if (currentPath.length > shortestLength) {
                     console.log("Skipping path - too long:", currentPath.length, ">", shortestLength);
                     continue;
                 }
                 
                 // If we reached the target
                 if (currentNode === endId) {
                     console.log("Reached target! Path:", currentPath, "Length:", currentPath.length);
                     if (currentPath.length < shortestLength) {
                         // Found shorter path, clear previous paths
                         console.log("Found shorter path, clearing previous paths");
                         shortestLength = currentPath.length;
                         allPaths.length = 0;
                         allPaths.push([...currentPath]);
                     } else if (currentPath.length === shortestLength) {
                         // Found another path of same length
                         console.log("Found another path of same length");
                         allPaths.push([...currentPath]);
                     }
                     continue;
                 }
                 
                 // Skip if we've visited this node in a shorter path
                 const pathKey = `${currentNode}-${currentPath.length}`;
                 if (visited.has(pathKey)) {
                     console.log("Skipping - already visited:", pathKey);
                     continue;
                 }
                 visited.add(pathKey);
                 
                 // Find all connected nodes (both directions)
                 const connectedNodes = [];
                 links.forEach(link => {
                     if (link.source.id === currentNode) {
                         connectedNodes.push(link.target.id);
                     } else if (link.target.id === currentNode) {
                         connectedNodes.push(link.source.id);
                     }
                 });
                 
                 console.log("Connected nodes for", currentNode, ":", connectedNodes);
                 
                 // Add paths to connected nodes
                 connectedNodes.forEach(nextNode => {
                     if (!currentPath.includes(nextNode)) { // Avoid cycles
                         const newPath = [...currentPath, nextNode];
                         console.log("Adding new path to queue:", newPath);
                         queue.push(newPath);
                     } else {
                         console.log("Skipping", nextNode, "- would create cycle");
                     }
                 });
             }
             
             console.log("BFS completed. All paths found:", allPaths);
             return allPaths;
         }

         function clearPathHighlight() {
             // Don't clear selectedNodes here - only clear visual highlighting
             node.classed('faded', false)
                 .classed('path-highlighted', false);
             link.classed('faded', false)
                 .classed('path-highlighted', false);
         }

         function clearAllPathSelection() {
             // This function clears everything including selected nodes
             selectedNodes = [];
             node.classed('faded', false)
                 .classed('path-highlighted', false)
                 .classed('path-selected', false);
             link.classed('faded', false)
                 .classed('path-highlighted', false);
             
             // Update path status indicator
             updatePathStatus();
         }

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