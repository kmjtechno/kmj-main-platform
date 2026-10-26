export default function CustomerLayoutUnavailable(): never {
    throw new Error(
        'Owner visual fixture unexpectedly selected the customer layout',
    );
}
