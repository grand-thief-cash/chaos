package consts

const (
	COMP_CTRL_TASK_MGMT = "task_mgmt_ctrl"
	COMP_SVC_SCHEDULER  = "scheduler_engine"
	COMP_SVC_EXECUTOR   = "executor"
	COMP_DAO_RUN        = "run_dao"
	COMP_DAO_TASK       = "task_dao"
	COMP_SVC_TASK       = "task_service" // new: task service with in-memory cache
	COMP_SVC_RUN        = "run_service"  // new: run service delegating to run dao
)
