export declare function pendingProjectCards(
    devices: ReadonlyArray<{
        id: string;
        name?: string | null;
        pending_projects?: ReadonlyArray<{
            id: string;
            name: string;
            status: 'pending_local_setup';
        }>;
    }> | null | undefined,
): Array<{
    key: string;
    sourceDeviceId: string;
    sourceDeviceName: string;
    projectId: string;
    projectName: string;
    status: 'pending_local_setup';
    registration: 'not_registered';
    connectionStatus: 'not_verified';
}>;
