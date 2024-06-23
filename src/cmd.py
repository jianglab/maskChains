from chimerax.core.commands import CmdDesc, ModelArg, FloatArg, StringArg
from chimerax.atomic import AtomicStructure
from chimerax.map import Volume

desc = CmdDesc(
    required=[("map", ModelArg),
                ("model", ModelArg),
                ("chain_ids", StringArg)],
    synopsis='Mask density map based on closest chains'
)

def maskChains(session, map, model, chain_ids):
    if not isinstance(map, Volume):
        session.logger.error("First argument must be a volume")
        return
    if not isinstance(model, AtomicStructure):
        session.logger.error("Second argument must be an atomic structure")
        return

    target_chains = chain_ids.split(',')

    chains = {}
    for _, chain_id, atoms in model.atoms.by_chain:
        chains[chain_id] = atoms.coords
    
    if len(chains)<3*len(target_chains):
        session.logger.warning(f"\tWARNING: mask {len(target_chains)} chains out of {len(chains)} chains. Are you sure there are at least one additional layer of chains below and above the target layer?")
    
    import numpy as np
    data = map.data.full_matrix()
    voxels = map.data.ijk_to_xyz(np.indices(data.shape).reshape(len(data.shape), -1).T[:, [2, 1, 0]])

    from scipy.spatial import KDTree
    for chain_id in chains:
        chains[chain_id] = KDTree(chains[chain_id])
    
    def available_cpu() -> int:
        import psutil
        cpu = max(1, int(psutil.cpu_count() * (1 - psutil.cpu_percent()/100)))
        return cpu
    cpu = available_cpu() 

    min_dist = np.ones(shape=data.shape, dtype=np.float32).flatten() * 1e10
    min_chain_id = np.empty(shape=data.shape, dtype=np.str_).flatten()
    for chain_id in chains:
        d, _ = chains[chain_id].query(x=voxels, workers=cpu)
        mask = np.where(d<min_dist)
        min_dist[mask] = d[mask]
        min_chain_id[mask] = chain_id

    mask = np.isin(min_chain_id, target_chains).reshape(data.shape)
    masked_data = data * mask
    
    from chimerax.map_data import ArrayGridData
    from chimerax.map import volume_from_grid_data
    grid = ArrayGridData(masked_data, origin = map.data.origin, step = map.data.step,
                         cell_angles = map.data.cell_angles, rotation = map.data.rotation,
                         name = map.name + " masked")
    masked_map = volume_from_grid_data(grid, session)
    masked_map.set_parameters(surface_levels=[map.surfaces[0].level])
    session.logger.info(f"Created masked map: {masked_map.name}")
    
    return masked_map
