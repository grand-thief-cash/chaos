export interface ArtemisTask {
  task_code: string;
  impl: string;
  module: string;
  is_dynamic?: boolean;
}

export interface TaskYaml {
  content: string;
}

export interface TaskUnitNode {
  name: string;
  path: string;
  type: 'file' | 'dir';
  children?: TaskUnitNode[];
}

export interface TaskUnitsTree {
  root: string;
  items: TaskUnitNode[];
}

export interface TaskUnitFile {
  path: string;
  content: string;
}

export interface TaskUnitRegisterReq {
  task_code: string;
  module: string;
  class_name: string;
}

export interface UnregisteredTask {
  module: string;
  class_name: string;
  task_code: string;
}
