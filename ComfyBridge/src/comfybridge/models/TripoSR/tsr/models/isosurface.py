from typing import Callable, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import mcubes   # ← using PyMCubes instead of torchmcubes


class IsosurfaceHelper(nn.Module):
    points_range: Tuple[float, float] = (0, 1)

    @property
    def grid_vertices(self) -> torch.FloatTensor:
        raise NotImplementedError


class MarchingCubeHelper(IsosurfaceHelper):
    def __init__(self, resolution: int) -> None:
        super().__init__()
        self.resolution = resolution
        self._grid_vertices: Optional[torch.FloatTensor] = None

    @property
    def grid_vertices(self) -> torch.FloatTensor:
        if self._grid_vertices is None:
            x, y, z = (
                torch.linspace(*self.points_range, self.resolution),
                torch.linspace(*self.points_range, self.resolution),
                torch.linspace(*self.points_range, self.resolution),
            )
            x, y, z = torch.meshgrid(x, y, z, indexing="ij")
            verts = torch.cat(
                [x.reshape(-1, 1), y.reshape(-1, 1), z.reshape(-1, 1)], dim=-1
            ).reshape(-1, 3)
            self._grid_vertices = verts
        return self._grid_vertices

    def forward(
        self,
        level: torch.FloatTensor,
    ) -> Tuple[torch.FloatTensor, torch.LongTensor]:

        # level shape: (res, res, res)
        level = -level.view(self.resolution, self.resolution, self.resolution)

        # move to CPU numpy for PyMCubes
        vol_np = level.detach().cpu().numpy()

        # run marching cubes
        # PyMCubes returns (vertices, triangles), both numpy arrays
        v_pos_np, t_pos_idx_np = mcubes.marching_cubes(vol_np, 0.0)

        # reorder vertices (TripoSR-specific convention)
        v_pos_np = v_pos_np[:, [2, 1, 0]]
        v_pos_np = v_pos_np / (self.resolution - 1.0)

        # convert back to PyTorch
        v_pos = torch.from_numpy(v_pos_np).float()
        t_pos_idx = torch.from_numpy(t_pos_idx_np.astype(np.int32))

        return v_pos.to(level.device), t_pos_idx.to(level.device)
